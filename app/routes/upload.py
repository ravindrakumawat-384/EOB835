from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from typing import List, Dict, Any
from ..utils.logger import get_logger
from app.services.file_validation import (
    calculate_file_hash,
    check_hash_exists,
    is_835_generated,
    register_uploaded_hash,
    is_valid_format
)
from app.services.s3_service import S3Service
from app.common.config import settings
from app.services.pg_upload_files import insert_upload_file, update_file_status, mark_processing_failed, get_pg_conn
from app.services.file_content_validator import comprehensive_file_validation
from ..services.auth_deps import get_current_user, require_role
from app.services.mongo_extraction import extract_json_ai, store_extraction_result
from app.services.file_text_extractor import extract_text_from_file
from app.services.ai_claim_extractor import ai_extract_claims, flatten_claims, flatten_claims2
from app.services.payer_template_service import get_or_create_payer, check_template_match, store_claims_in_postgres
import mimetypes
from app.common.db.db import init_db
import uuid
import datetime
import app.common.db.db as db_module


DB = init_db()

logger = get_logger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

# S3 configuration (replace with your actual credentials and bucket)
S3_BUCKET = settings.S3_BUCKET
AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY 
AWS_REGION = settings.AWS_REGION
s3_client = S3Service(S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

@router.post("/files", status_code=status.HTTP_200_OK)
# async def upload_files(user: Dict[str, Any] = Depends(get_current_user), files: List[UploadFile] = File(...)) -> Dict[str, Any]:

async def upload_files(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    """
    Upload one or more files, validate size, corruption, hash, and format.
    Returns status and message per file.
    """
    responses = []
    ext_collection = db_module.db["extraction_results"]  
    claim_version = db_module.db["claim_version"]  
    for file in files:
        # 1. Check file size
        if file.size and file.size > MAX_FILE_SIZE:
            responses.append({"filename": file.filename, "status": "error", "message": "File too large (max 50MB)"})
            continue
        try:
            content = await file.read()
        except Exception:
            responses.append({"filename": file.filename, "status": "error", "message": "File is corrupted"})
            continue
        if len(content) > MAX_FILE_SIZE:
            responses.append({"filename": file.filename, "status": "error", "message": "File too large (max 50MB)"})
            continue
        # 2. Hash check
        file_hash = calculate_file_hash(content)
        if check_hash_exists(file_hash):
            if is_835_generated(file_hash):
                responses.append({"filename": file.filename, "status": "error", "message": "Already generated"})
                continue
        # 3. Format/requirement check
        if not is_valid_format(content):
            responses.append({"filename": file.filename, "status": "error", "message": "File is not valid."})
            continue
        # 4. Register hash (simulate DB insert)
        register_uploaded_hash(file_hash)
        # 5. Save file and metadata (to S3)
        s3_path = s3_client.upload_file(content, file.filename)
        if not s3_path:
            responses.append({"filename": file.filename, "status": "error", "message": "Failed to upload to S3"})
            continue
        # 6. Store metadata in PostgreSQL
        # Replace these with actual values from context/session/request
        org_id = "9ac493f7-cc6a-4d7d-8646-affb00ed58da"
        # org_id = "57a0f4e2-8076-4910-8259-9d06338965e9"
        batch_id = None
        mime_type = file.content_type or "application/octet-stream"
        logger.info(f"Processing file: {file.filename}, size: {len(content)}, mime_type: {mime_type}")
        file_size = len(content)
        upload_source = "manual"
        # uploaded_by = "b729c531-7c90-4602-b541-e910d45b0a0d"  
        uploaded_by = "e3a84bea-8c81-47fa-9009-ca71e94105d8"
        # uploaded_by = "57a0f4e2-8076-4910-8259-9d06338965e9"  
        file_id = insert_upload_file(
            org_id=org_id,
            batch_id=batch_id,
            filename=file.filename,
            s3_path=s3_path,
            mime_type=mime_type,
            file_size=file_size,
            file_hash=file_hash,
            upload_source=upload_source,
            uploaded_by=uploaded_by,
            status="pending_review"  # Set status to "Pending Review" on first upload
        )
        logger.info(f" File inserted with ID: {file_id} (hash: {file_hash})")

        pg = get_pg_conn()
        cur = pg.cursor()
        cur.execute("SELECT name FROM payers WHERE org_id = %s", (org_id,))
        payer_names = cur.fetchall()
        cur.close()
        pg.close()

        print('payer_names----->', str(payer_names[0]))

        # 7. Extract text from file (universal for PDF, DOCX, TXT, image)

        raw_text = extract_text_from_file(content, file.filename, mime_type)
        logger.info(f"Extracted text for {file.filename} (first 200 chars): {raw_text[:200]}")
        

        print()
        print()
        print()
        print()
        print()
        print()
        print("Raw text operation start=======================")
        print("Raw text operation start=======================")
        print("Raw text operation start=======================")
        print()
        print()

        import re
        from typing import List

        def split_claim_blocks(raw_text: str) -> List[str]:
            """
            Deterministically split raw OCR text into claim-level blocks.
            """
            blocks = re.split(
                r'(?=Patient Name:|CLAIM NO\.|Claim Number:)',
                raw_text
            )

            # Remove garbage headers
            return [b.strip() for b in blocks if len(b.strip()) > 200]

        # print("Splited Raws text========>>  ", split_claim_blocks(raw_text))


        print()
        print()
        print("Raw text operation End===========================")
        print("Raw text operation End===========================")
        print("Raw text operation End===========================")
        print()
        print()
        print()
        print()
        print()
        print()










        # Check if any payer name is present in the extracted text
        matched_payer_name = ''
        if payer_names and raw_text:
            for payer_tuple in payer_names:
                print('payer_tuple----->', payer_tuple)
                print('payer_tuple----->', payer_tuple[0])
                payer_db_name = payer_tuple[0]
                print('payer_db_name----->', payer_db_name)
                if payer_db_name and payer_db_name.lower() in raw_text.lower():
                    matched_payer_name = payer_db_name
                    break
        print('Matched payer name in extracted text:', matched_payer_name)
        print('Matched payer name in extracted text:', matched_payer_name)
        print('Matched payer name in extracted text:', matched_payer_name)
        print('Matched payer name in extracted text:', matched_payer_name)
        print('Matched payer name in extracted text:', matched_payer_name)
        print('Matched payer name in extracted text:', matched_payer_name)

        pg = get_pg_conn()
        cur = pg.cursor()
        cur.execute("SELECT id FROM payers WHERE name = %s AND org_id = %s", (matched_payer_name, org_id))
        payer_id = cur.fetchone()
        if payer_id:
            print("==if==")
            cur.execute("SELECT id FROM templates WHERE payer_id = %s", (payer_id,))
            template_id = cur.fetchone()
        else:
            print("==else==")
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

            return {"message": "Template are not available of this file."}
        cur.close()
        pg.close()

        ext_collection = DB["template_builder_sessions"] 
        temp_data = await ext_collection.find_one({"template_id": template_id[0]})
        dynamic_key = temp_data.get("dynamic_keys", []) if temp_data else []
        
        # 7.5. Quick text readability check
        if not raw_text or len(raw_text.strip()) < 50:
            logger.error(f"File {file.filename} appears unreadable - insufficient text content")
            logger.info(f"Attempting to mark file {file_id} as processing failed (text extraction)")
            update_success = mark_processing_failed(file_id, "Insufficient text content extracted from file", "text_extraction")
            logger.info(f" Database update result: {update_success}")
            responses.append({
                "filename": file.filename,
                "status": "error",
                "message": "File appears unreadable - insufficient text content",
                "file_id": file_id
            })
            continue
        
        # 8. AI extraction: use AI model to convert text to JSON




        # operation start
        print("===============================================")


        print("Starting AI extraction for file:", file.filename)
        print("Using dynamic keys:", dynamic_key)
        print("Extracted raw text (first 500 chars):", raw_text)

        print("===============================================")
        # operation end




        print()
        print()
        print()
        print()
        print()
        print()
        print("End End End End End End End End End End End End End ................................................")
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print()


        claims = []
        flat_claims_list = []
        # ai_result = []
        for claim_text in split_claim_blocks(raw_text):
            # print("Claim Text for AI extraction:", claim_text)
            print()
            claim_json = ai_extract_claims(claim_text,dynamic_key)
            # print("Extracted Claim JSON:", claim_json)
            claims.append(claim_json)

            print("Flattened claims start---> ")
            f_claims = flatten_claims2(claim_json)
            flat_claims_list.append(f_claims)
            print("Flattened claims End---> ")

        print()
        print()
        # print("claims==================>>  ", claims)
        print()
        print()


        # print("Flattened claims start---> ")
        # for claim in claims:
        #     print("Individual claim before flattening:", claim)
        #     print()
        #     flat_claims = flatten_claims2(claim)
        #     print("Flattened claims:", flat_claims)
        #     print()
        #     print()


        
        # print("AI extraction result start---> ")
        # ai_result = ai_extract_claims(raw_text, dynamic_key)
        # print("AI extraction result:", ai_result)
        # print()
        # # flat_claims = flatten_claims(ai_result)
        # print("Flattened claims start---> ")
        # flat_claims = flatten_claims2(ai_result)
        # print("Flattened claims:", flat_claims)
        # print()
        # print()



        payer_name = None
        # if flat_claims:
        if flat_claims_list:
            payer_name = matched_payer_name


        # # If uploaded file is JSON, extract payer name and update detected_payer_id
        # if ai_result and isinstance(ai_result, dict):
        #     # Try to get payer name from top-level or claims
        #     # payer_info = ai_result.get('fields')
        #     # print("payer_info:11", payer_info)
        #     # payer_info = ai_result.get('fields')[0]
        #     # print("payer_info:22", payer_info)
        #     # payer_name = payer_info.get('name')
        #     if not payer_name and 'claims' in ai_result and isinstance(ai_result['claims'], list) and ai_result['claims']:
        #         payer_name = ai_result['claims'][0].get('payer_name')


        if payer_name:

            # Check if payer exists in payer table
            from app.services.payer_template_service import get_or_create_payer
            payer_id = get_or_create_payer(payer_name, org_id)
            if payer_id:
                # Update detected_payer_id in upload_files table
                import psycopg2
                pg = get_pg_conn()
                cur = pg.cursor()
                cur.execute("UPDATE upload_files SET detected_payer_id = %s WHERE id = %s", (payer_id, file_id))
                pg.commit()
                cur.close()
                pg.close()

        # 10. Store each claim JSON as a separate document in MongoDB extraction_result collection
        # Store all claims in extraction_results collection as separate documents

        for ai_result in claims:
            mongo_doc_ids = store_extraction_result(file_id, ai_result, payer_name, uploaded_by)
            
        # mongo_doc_ids = store_extraction_result(file_id, ai_result, raw_text, payer_name, uploaded_by) if flat_claims else []

        # 11. Process payers and templates
        payer_template_status = {}
        detected_template_version_id = None
        payer_id = None

        for flat_claims in flat_claims_list:

            if flat_claims:
                print("Processing payer and template matching...")
                first_claim = flat_claims
                payer_name = first_claim.get('payer_name')
                if payer_name:
                    print(f"payer name ===============: {payer_name}")
                    payer_id = get_or_create_payer(payer_name, org_id)
                    print(f"payer_id ===============: {payer_id}")
                    # Find all template_ids for this payer
                    # from app.services.pg_upload_files import get_pg_conn  # Removed to avoid UnboundLocalError
                    pg = get_pg_conn()
                    cur = pg.cursor()
                    cur.execute("SELECT id FROM templates WHERE payer_id = %s", (payer_id,))
                    template_ids = [str(row[0]) for row in cur.fetchall()]
                    print("template_ids ===============:", template_ids)
                    cur.close()
                    pg.close()

                    sessions_collection = DB['template_builder_sessions']
                    cursor = sessions_collection.find({"template_id": {"$in": template_ids}})
                    template_sessions = await cursor.to_list(length=None)
                    claim_keys = list(first_claim.keys())
                    from app.services.payer_template_service import keys_match_template
                    best_match = None
                    best_frac = 0.0
                    for session in template_sessions:
                        dynamic_keys = session.get("dynamic_keys", [])
                        print(f"Checking session {session.get('_id')} with dynamic keys: {dynamic_keys}")
                        if not dynamic_keys:
                            continue
                        
                        # Extract flat key names from sections structure
                        flat_key_names = []
                        if isinstance(dynamic_keys, list) and len(dynamic_keys) > 0:
                            if isinstance(dynamic_keys[0], dict):  # Section-based format
                                for section in dynamic_keys:
                                    if isinstance(section, dict) and "fields" in section:
                                        for field in section.get("fields", []):
                                            if isinstance(field, dict) and "field" in field:
                                                flat_key_names.append(field["field"])
                            else:  # Legacy flat list format
                                flat_key_names = [k for k in dynamic_keys if isinstance(k, str)]
                        
                        if not flat_key_names:
                            continue
                        
                        extracted_set = set([k.lower() for k in claim_keys if k])
                        template_set = set([k.lower() for k in flat_key_names if k])

                        matched = extracted_set.intersection(template_set)
                        frac = len(matched) / max(1, len(template_set))
                        if frac > best_frac:
                            best_frac = frac
                            best_match = session
                    # mongo_client.close()
                    if best_match and best_frac > 0:
                        detected_template_version_id = best_match.get("_id")
                        print(f"Attempting to update upload_files: file_id={file_id}, detected_template_version_id={detected_template_version_id}, match_percentage={best_frac*100:.2f}%")
                        logger.info(f"Attempting to update upload_files: file_id={file_id}, detected_template_version_id={detected_template_version_id}, match_percentage={best_frac*100:.2f}%")
                        pg = get_pg_conn()
                        cur = pg.cursor()
                        cur.execute("UPDATE upload_files SET detected_template_version_id = %s WHERE id = %s", (detected_template_version_id, file_id))
                        pg.commit()
                        print(f"Update result: {cur.rowcount} row(s) affected.")
                        logger.info(f"Update result: {cur.rowcount} row(s) affected.")
                        cur.close()
                        pg.close()
                    template_status = check_template_match(payer_id, list(first_claim.keys()))
                    payer_template_status = {
                        "payer_id": payer_id,
                        "template_status": template_status,
                        "detected_template_version_id": detected_template_version_id
                    }

            # 12. Store claims in PostgreSQL
            claim_ids = store_claims_in_postgres(file_id, flat_claims, org_id, payer_id, payer_name)

            # 13. Update file status to processed if everything succeeded
            update_file_status(file_id, "pending_review")

        # Log AI extraction results
        # logger.info(f"AI extraction confidence: {ai_result.get('confidence', 0)}%")
        print()
        print()
        print("````````````````````````````````````````````````````")
        print("`````````````````````Server End`````````````````````")
        print("````````````````````````````````````````````````````")
        print()
        print()
        # responses.append({
        #     "filename": file.filename,
        #     "status": "success",
        #     "message": "File uploaded, validated, and processed.",
        #     "s3_path": s3_path,
        #     "file_id": file_id,
        #     "mongo_doc_ids": mongo_doc_ids,
        #     "claims_count": len(flat_claims),
        #     "claim_ids": claim_ids,
        #     "payer_template_status": payer_template_status
        # })
    return {"success": "File Upload successfully."}
