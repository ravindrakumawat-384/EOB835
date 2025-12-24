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

logger = get_logger(__name__)

async def process_single_file_async(file_record):
    """
    Async logic for processing a single file.
    """
    file_id, org_id, storage_path, filename, status, uploaded_at, uploaded_by = file_record
    
    # Initialize MongoDB client locally for this task
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    
    try:
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
        print(f'📝 Extracted text length: {len(raw_text)} characters')
        if not raw_text or len(raw_text.strip()) < 50:
            logger.error(f"File {filename} appears unreadable")
            print(f"❌ Text extraction failed - insufficient content")
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
        print(f"🔍 Matching payer from {len(payer_names)} available payers...")
        for p_name in payer_names:
            if p_name and p_name.lower() in raw_text.lower():
                matched_payer_name = p_name
                break

        if not matched_payer_name:
            logger.warning(f"No payer matched for file {file_id}")
            print(f"⚠️  No payer matched - marking as need_template")
            update_file_status(file_id, 'need_template')
            return False

        print(f"✓ Matched payer: {matched_payer_name}")

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
            """
            UPDATE upload_files
            SET detected_payer_id = %s
            WHERE id = %s
            """,
            (payer_id, file_id)
        )
        pg.commit()
        
        cur.execute("SELECT id FROM templates WHERE payer_id = %s", (payer_id,))
        template_row = cur.fetchone()
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
            """
            ROOT FIX: Split text into individual claim blocks with ONLY payment header.

            Problem: Old logic included first claim in "header", polluting all blocks with
            multiple claim numbers. AI would then extract the first claim number from every block.

            Solution:
            1. Find position of first claim in document
            2. Extract TRUE header (only payment/payer info before first claim)
            3. Split remaining text by PatientName or ClaimNumber patterns
            4. Append TRUE header (without any claim data) to each claim block

            This ensures each block contains EXACTLY ONE claim, not all claims.
            """
            # Find the position of the first claim (first occurrence of ClaimNumber/Claim Number)
            first_claim_match = re.search(r'(?:ClaimNumber|Claim Number)[\s:]*[A-Z]?\d{8,}', text, re.IGNORECASE)

            if not first_claim_match:
                # No claims found, return whole text
                return [text.strip()] if len(text.strip()) > 50 else []

            first_claim_pos = first_claim_match.start()

            # Find the start of that claim by looking backwards for PatientName
            header_end = text.rfind('PatientName', 0, first_claim_pos)
            if header_end == -1:
                header_end = text.rfind('Patient Name', 0, first_claim_pos)
            if header_end == -1:
                # Couldn't find PatientName before ClaimNumber, use position right before claim
                header_end = first_claim_pos

            # Extract TRUE header (everything before first claim - only payment/payer info)
            true_header = text[:header_end].strip()

            # Split remaining text by PatientName patterns
            remaining_text = text[header_end:]

            # Try multiple splitting patterns for different PDF formats
            claim_pattern = r'(?=PatientName[\s:]+[A-Z])'
            claim_blocks = re.split(claim_pattern, remaining_text, flags=re.IGNORECASE)

            # If PatientName split didn't work, try Patient Name with space
            if len(claim_blocks) <= 1:
                claim_pattern = r'(?=Patient Name[\s:]+[A-Z])'
                claim_blocks = re.split(claim_pattern, remaining_text, flags=re.IGNORECASE)

            # Filter valid claim blocks (must have reasonable content)
            valid_claims = [b.strip() for b in claim_blocks if len(b.strip()) > 50]

            # Append TRUE header (payment info only) to each claim
            if true_header and len(true_header) > 20:
                processed = []
                for claim in valid_claims:
                    processed.append(true_header + "\n" + ("-" * 20) + "\n" + claim)
                return processed
            else:
                # No header found, return claims as-is
                return valid_claims

        claim_blocks = split_claim_blocks(raw_text)
        print(f"📄 Split into {len(claim_blocks)} claim block(s)")

        # AI Extraction
        sem = asyncio.Semaphore(3)
        async def extract_with_sem(block):
            async with sem:
                await asyncio.sleep(0.5)
                return await ai_extract_claims(block, dynamic_key)

        print(f"🤖 Starting AI extraction for {len(claim_blocks)} block(s)...")
        tasks = [extract_with_sem(block) for block in claim_blocks]
        claims = await asyncio.gather(*tasks)
        print(f"✓ AI extraction completed")

        # Process and store results
        stored_count = 0
        duplicate_count = 0
        skipped_empty = 0

        for idx, ai_result in enumerate(claims, 1):
            # Store in MongoDB (async)
            await store_extraction_result(db, file_id, ai_result, matched_payer_name, uploaded_by)

            # Flatten and store in Postgres (sync)
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
        return True
        
    except Exception as file_error:
        logger.error(f"Error processing file {file_id}: {file_error}", exc_info=True)
        mark_processing_failed(file_id, str(file_error), "processing_error")
        return False
    finally:
        client.close()

@celery_app.task(name='app.tasks.file_processor.process_pending_files')
def process_pending_files():
    print("\n" + "=" * 80)
    print("🔄 CELERY PERIODIC TASK STARTED - Processing pending files")
    print("=" * 80)
    try:
        logger.info("=" * 60)
        logger.info("CELERY PERIODIC TASK STARTED - Processing pending files")
        logger.info("=" * 60)

        # Connect to database
        conn = get_pg_conn()
        cur = conn.cursor()

        # Find files that need processing
        cur.execute("""
            SELECT id, org_id, storage_path, original_filename, processing_status, uploaded_at, uploaded_by
            FROM upload_files
            WHERE processing_status IN ('ai_processing')
            ORDER BY uploaded_at ASC
            LIMIT 10
        """)

        files = cur.fetchall()

        if not files:
            print("ℹ️  No pending files found to process")
            logger.info("No pending files found to process")
            cur.close()
            conn.close()
            return {'status': 'no_files'}

        print(f"\n📂 Found {len(files)} file(s) to process:")
        for idx, f in enumerate(files, 1):
            print(f"   {idx}. File ID: {f[0]}, Filename: {f[3]}, Status: {f[4]}")

        cur.close()
        conn.close()

        print(f"\n🔒 Locked {len(files)} file(s) for processing")
        logger.info(f"Locked {len(files)} file(s) for processing")
        
        # Process each file
        processed_count = 0
        for idx, file_record in enumerate(files, 1):
            file_id, org_id, storage_path, filename, status, uploaded_at, uploaded_by = file_record
            print(f"\n{'='*80}")
            print(f"📄 Processing file {idx}/{len(files)}")
            print(f"   File ID: {file_id}")
            print(f"   Filename: {filename}")
            print(f"   Org ID: {org_id}")
            print(f"   Storage Path: {storage_path}")
            print(f"{'='*80}")

            # Use asyncio.run for each file to ensure fresh event loop
            success = asyncio.run(process_single_file_async(file_record))
            if success:
                processed_count += 1
                print(f"✅ Successfully processed: {filename}")
            else:
                print(f"❌ Failed to process: {filename}")

        print(f"\n{'='*80}")
        print(f"🎯 TASK COMPLETED: Processed {processed_count}/{len(files)} file(s)")
        print(f"{'='*80}\n")
        logger.info(f"Processed {processed_count} file(s)")
        return {'status': 'success', 'processed': processed_count}

    except Exception as e:
        print(f"\n❌ ERROR in periodic task: {e}")
        logger.error(f"Error in periodic task: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}
