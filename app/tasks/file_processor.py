from app.celery_config import celery_app
from app.services.pg_upload_files import update_file_status, mark_processing_failed
from app.utils.logger import get_logger
from app.services.s3_service import S3Service
from app.common.config import settings
from app.services.file_text_extractor import extract_text_from_file
from app.services.payer_template_service import get_or_create_payer, check_template_match, store_claims_in_postgres
from app.services.ai_claim_extractor import ai_extract_claims, flatten_claims2
from app.common.db.db import init_db
from app.common.db.pg_db import get_pg_conn
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
import datetime
import asyncio
import mimetypes
import re
from typing import List
from app.services.mongo_extraction import store_extraction_result

import json
import time
from app.common.db.redis_db import get_redis_client

logger = get_logger(__name__)
DB = init_db()

# Redis Key Constants
PROCESSING_JOB_IDS = "processing_job_ids"
JOB_STATE_PREFIX = "job_state:"
MAX_RETRIES = 3
RETRY_DELAY = 300  # 5 minutes in seconds
JOB_TIMEOUT = 600  # 10 minutes in seconds

async def process_single_file_async(file_record):
    """
    Async logic for processing a single file.
    """
    file_id, org_id, storage_path, filename, status, uploaded_at, uploaded_by = file_record
    redis_client = get_redis_client()
    job_key = f"{JOB_STATE_PREFIX}{file_id}"
    
    # Initialize MongoDB client locally for this task
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    
    try:
        # Update state to RUNNING
        state = json.loads(redis_client.get(job_key) or "{}")
        state.update({
            "status": "RUNNING",
            "last_run": time.time(),
            "retry_count": state.get("retry_count", 0)
        })
        redis_client.set(job_key, json.dumps(state))

        # Initialize S3 service
        s3_service = S3Service(
            settings.S3_BUCKET,
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_REGION
        )
        
        # Download file content from S3
        logger.info(f"Downloading file from S3: {storage_path}")
        file_content = s3_service.download_file(storage_path)
        
        # Determine mime type
        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        
        # Extract text
        raw_text = extract_text_from_file(file_content, filename, mime_type)
        if not raw_text or len(raw_text.strip()) < 50:
            logger.error(f"File {filename} appears unreadable")
            mark_processing_failed(file_id, "Insufficient text content", "text_extraction")
            return False

        # Get payers for this org
        pg = get_pg_conn()
        cur = pg.cursor()
        cur.execute("SELECT name FROM payers WHERE org_id = %s", (org_id,))
        payer_names = [row[0] for row in cur.fetchall()]
        cur.close()
        pg.close()

        # Match payer
        matched_payer_name = ''
        for p_name in payer_names:
            if p_name and p_name.lower() in raw_text.lower():
                matched_payer_name = p_name
                break

        if not matched_payer_name:
            update_file_status(file_id, 'need_template')
            return False

        # Get template for payer
        pg = get_pg_conn()
        cur = pg.cursor()
        cur.execute("SELECT id FROM payers WHERE name = %s AND org_id = %s", (matched_payer_name, org_id))
        payer_row = cur.fetchone()
        if not payer_row:
            update_file_status(file_id, 'need_template')
            cur.close()
            pg.close()
            return False
        
        payer_id = payer_row[0]
        cur.execute(
            "UPDATE upload_files SET detected_payer_id = %s WHERE id = %s",
            (payer_id, file_id)
        )
        pg.commit()
        
        # cur.execute("SELECT id FROM templates WHERE payer_id = %s", (payer_id,))
        # template_row = cur.fetchone()


        if payer_id:
            cur.execute("SELECT id FROM templates WHERE payer_id = %s", (payer_id,))
            template_row = cur.fetchone()
        else:
            ext_collection = DB["extraction_results"]  
            claim_version = DB["claim_version"] 
            cur.execute(
                """
                UPDATE upload_files
                SET processing_status = %s
                WHERE id = %s
                """,
                ('need_template', file_id)
            )

            pg.commit()
            claim_doc = {
            "_id": str(uuid.uuid4()),
            "fileId": file_id,
            "rawExtracted": '',
            "claim": '',
            "aiConfidence": 0,
            "extractionStatus": "",
            "payerName": '',
            "claimNumber": 0,
            "totalExtractedAmount": 0,
            "createdAt": datetime.datetime.utcnow(),
            "status": "need_template",
            "reviewerId": uploaded_by
            }
            ext_collection.insert_one(claim_doc)

            claim_version.insert_one({
            "file_id": file_id,
            "extraction_id": claim_doc['_id'],
            "version": "1.0",
            "claim": '',
            "created_at": datetime.datetime.utcnow(),
            "updated_by": uploaded_by,
            "status": "need_template"})




        cur.close()
        pg.close()

        if not template_row:
            update_file_status(file_id, 'need_template')
            return False
        
        template_id = template_row[0]
        
        # Get dynamic keys from MongoDB
        sessions_collection = db["template_builder_sessions"]
        temp_data = await sessions_collection.find_one({"template_id": str(template_id)})
        dynamic_key = temp_data.get("dynamic_keys", []) if temp_data else []

        # Split into claim blocks
        def split_claim_blocks(text: str) -> List[str]:
            first_claim_match = re.search(r'(?:ClaimNumber|Claim Number)[\s:]*[A-Z]?\d{8,}', text, re.IGNORECASE)
            if not first_claim_match:
                return [text.strip()] if len(text.strip()) > 50 else []

            first_claim_pos = first_claim_match.start()
            header_end = text.rfind('PatientName', 0, first_claim_pos)
            if header_end == -1:
                header_end = text.rfind('Patient Name', 0, first_claim_pos)
            if header_end == -1:
                header_end = first_claim_pos

            true_header = text[:header_end].strip()
            remaining_text = text[header_end:]
            claim_pattern = r'(?=PatientName[\s:]+[A-Z])'
            claim_blocks = re.split(claim_pattern, remaining_text, flags=re.IGNORECASE)
            if len(claim_blocks) <= 1:
                claim_pattern = r'(?=Patient Name[\s:]+[A-Z])'
                claim_blocks = re.split(claim_pattern, remaining_text, flags=re.IGNORECASE)

            valid_claims = [b.strip() for b in claim_blocks if len(b.strip()) > 50]
            if true_header and len(true_header) > 20:
                return [true_header + "\n" + ("-" * 20) + "\n" + claim for claim in valid_claims]
            return valid_claims

        claim_blocks = split_claim_blocks(raw_text)

        # AI Extraction
        sem = asyncio.Semaphore(3)
        async def extract_with_sem(block):
            async with sem:
                await asyncio.sleep(0.5)
                return await ai_extract_claims(block, dynamic_key)

        tasks = [extract_with_sem(block) for block in claim_blocks]
        claims = await asyncio.gather(*tasks)

        # Process and store results
        stored_count = 0
        duplicate_count = 0
        skipped_empty = 0

        for idx, ai_result in enumerate(claims, 1):
            await store_extraction_result(db, file_id, ai_result, matched_payer_name, uploaded_by)
            flat_claims = flatten_claims2(ai_result)

            if flat_claims:
                claim_number = flat_claims.get("claim_number")
                patient_name = flat_claims.get("patient_name")

                # PRODUCTION FIX: STRICT VALIDATION - Claim number is MANDATORY
                if not claim_number or claim_number.startswith("MISSING-"):
                    skipped_empty += 1
                    logger.error(
                        f"Block {idx}/{len(claims)}: AI extraction failed - no valid claim number. "
                        f"Patient: {patient_name or 'N/A'}. This indicates AI extraction error."
                    )
                    print(f"   ❌ Block {idx}/{len(claims)}: FAILED - no claim number extracted")
                    continue

                # Validate patient name (warning only, not blocking)
                if not patient_name or len(patient_name.strip()) < 2:
                    logger.warning(
                        f"Block {idx}/{len(claims)}: Missing patient name for claim {claim_number}"
                    )

                display_claim = claim_number
                print(f" Storing claim {idx}/{len(claims)}: {display_claim}")

                result = store_claims_in_postgres(file_id, flat_claims, org_id, payer_id, matched_payer_name)
                if result:
                    stored_count += 1
                    logger.info(f"Successfully stored claim {claim_number}")
                else:
                    duplicate_count += 1
                    logger.warning(f"Duplicate claim skipped: {claim_number}")
                    print(f"   ⚠️  Duplicate skipped: {claim_number}")

        print(f"✓ Stored {stored_count} new claim(s), skipped {duplicate_count} duplicate(s), {skipped_empty} empty extraction(s)")

        # Update status
        update_file_status(file_id, "pending_review", payer_id)
        
        # SUCCESS: Remove from Redis
        redis_client.srem(PROCESSING_JOB_IDS, file_id)
        redis_client.delete(job_key)
        return True
        
    except Exception as file_error:
        logger.error(f"Error processing file {file_id}: {file_error}", exc_info=True)
        mark_processing_failed(file_id, str(file_error), "processing_error")
        
        # FAILURE: Update state to FAILED, keep in processing_job_ids
        state = json.loads(redis_client.get(job_key) or "{}")
        state.update({
            "status": "FAILED",
            "error": str(file_error),
            "retry_count": state.get("retry_count", 0) + 1
        })
        redis_client.set(job_key, json.dumps(state))
        return False
    finally:
        client.close()

@celery_app.task(name='app.tasks.file_processor.process_pending_files')
def process_pending_files():
    logger.info("CELERY PERIODIC TASK STARTED - Processing pending files")
    redis_client = get_redis_client()
    
    try:
        # Connect to database
        conn = get_pg_conn()
        cur = conn.cursor()

        # Find files that need processing
        cur.execute("""
            SELECT id, org_id, storage_path, original_filename, processing_status, uploaded_at, uploaded_by
            FROM upload_files
            WHERE processing_status IN ('ai_processing')
            ORDER BY uploaded_at ASC
            LIMIT 20
        """)
        files = cur.fetchall()
        cur.close()
        conn.close()

        if not files:
            return {'status': 'no_files'}

        processed_count = 0
        for file_record in files:
            file_id = file_record[0]
            job_key = f"{JOB_STATE_PREFIX}{file_id}"
            
            # ATOMIC CHECK & ADD
            is_new = redis_client.sadd(PROCESSING_JOB_IDS, file_id)
            
            if not is_new:
                # Job already in Redis, check state
                state_raw = redis_client.get(job_key)
                if not state_raw:
                    # Inconsistent state, re-add state
                    redis_client.set(job_key, json.dumps({"status": "RUNNING", "last_run": time.time(), "retry_count": 0}))
                    continue
                
                state = json.loads(state_raw)
                
                # Check for CRASH (Timeout)
                if state.get("status") == "RUNNING":
                    if time.time() - state.get("last_run", 0) > JOB_TIMEOUT:
                        logger.warning(f"Job {file_id} timed out. Retrying...")
                    else:
                        logger.info(f"Job {file_id} is already running. Skipping.")
                        continue
                
                # Check for RETRY
                elif state.get("status") == "FAILED":
                    if state.get("retry_count", 0) >= MAX_RETRIES:
                        logger.error(f"Job {file_id} reached max retries. Skipping.")
                        continue
                    
                    if time.time() - state.get("last_run", 0) < RETRY_DELAY:
                        logger.info(f"Job {file_id} failed recently. Waiting for backoff.")
                        continue
                    
                    logger.info(f"Retrying failed job {file_id} (Attempt {state.get('retry_count') + 1})")
                
                else:
                    continue

            else:
                # New job, initialize state
                redis_client.set(job_key, json.dumps({"status": "RUNNING", "last_run": time.time(), "retry_count": 0}))

            # Process the file
            success = asyncio.run(process_single_file_async(file_record))
            if success:
                processed_count += 1

        return {'status': 'success', 'processed': processed_count}

    except Exception as e:
        logger.error(f"Error in periodic task: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}
