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
from app.services.pg_upload_files import insert_upload_file, update_file_status, mark_processing_failed
from app.services.file_content_validator import comprehensive_file_validation
from ..services.auth_deps import get_current_user, require_role
from app.services.mongo_extraction import extract_json_ai, store_extraction_result
from app.services.file_text_extractor import extract_text_from_file
from app.services.ai_claim_extractor import ai_extract_claims, flatten_claims
from app.services.payer_template_service import get_or_create_payer, check_template_match, store_claims_in_postgres
import mimetypes

router = APIRouter(prefix="/upload", tags=["upload"])
logger = get_logger(__name__)

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
        uploaded_by = "b729c531-7c90-4602-b541-e910d45b0a0d" 
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
        logger.info(f"📋 File inserted with ID: {file_id} (hash: {file_hash})")
        # 7. Extract text from file (universal for PDF, DOCX, TXT, image)
        raw_text = extract_text_from_file(content, file.filename, mime_type)
        logger.info(f"Extracted text for {file.filename} (first 200 chars): {raw_text[:200]}")
        
        # 7.5. Quick text readability check
        if not raw_text or len(raw_text.strip()) < 50:
            logger.error(f"File {file.filename} appears unreadable - insufficient text content")
            logger.info(f"🔄 Attempting to mark file {file_id} as processing failed (text extraction)")
            update_success = mark_processing_failed(file_id, "Insufficient text content extracted from file", "text_extraction")
            logger.info(f"📊 Database update result: {update_success}")
            responses.append({
                "filename": file.filename,
                "status": "error",
                "message": "File appears unreadable - insufficient text content",
                "file_id": file_id
            })
            continue
        
        # 8. AI extraction: extract claims from text (AI ONLY)
        try:
            ai_result = ai_extract_claims(raw_text)
            flat_claims = flatten_claims(ai_result)
        except Exception as e:
            logger.error(f"AI extraction failed for {file.filename}: {str(e)}")
            mark_processing_failed(file_id, f"AI extraction failed: {str(e)}", "ai_processing")
            responses.append({
                "filename": file.filename,
                "status": "error",
                "message": f"AI extraction failed: {str(e)}",
                "file_id": file_id
            })
            continue
        
        # 9. Comprehensive validation of file processing
        is_valid, validation_error = comprehensive_file_validation(raw_text, ai_result, file.filename)
        if not is_valid:
            logger.error(f"File validation failed for {file.filename}: {validation_error}")
            logger.info(f"🔄 Attempting to mark file {file_id} as processing failed (validation)")
            update_success = mark_processing_failed(file_id, validation_error, "validation")
            logger.info(f"📊 Database update result: {update_success}")
            responses.append({
                "filename": file.filename,
                "status": "error",
                "message": f"File validation failed: {validation_error}",
                "file_id": file_id
            })
            continue
        
        # Log AI extraction results
        logger.info(f"AI extraction confidence: {ai_result.get('confidence', 0)}%")
        
        try:
            # 10. Store extraction result in MongoDB (original AI result + flat claims)
            mongo_doc_id = store_extraction_result(file_id, ai_result, raw_text)
            
            # 11. Process payers and templates
            payer_template_status = {}
            if flat_claims:
                first_claim = flat_claims[0]
                payer_name = first_claim.get('payer_name')
                if payer_name:
                    payer_id = get_or_create_payer(payer_name, org_id)
                    template_status = check_template_match(payer_id, list(first_claim.keys()))
                    payer_template_status = {
                        "payer_id": payer_id,
                        "template_status": template_status
                    }
            
            # 12. Store claims in PostgreSQL
            claim_ids = store_claims_in_postgres(file_id, flat_claims, org_id)
            
            # 13. Update file status to processed if everything succeeded
            update_file_status(file_id, "processed")
            
        except Exception as e:
            logger.error(f"Error during database operations for {file.filename}: {str(e)}")
            # Update file status to failed if database operations fail
            mark_processing_failed(file_id, f"Database operation failed: {str(e)}", "database_storage")
            responses.append({
                "filename": file.filename,
                "status": "error",
                "message": f"Database operation failed: {str(e)}",
                "file_id": file_id
            })
            continue
        
        responses.append({
            "filename": file.filename,
            "status": "success",
            "message": "File uploaded, validated, and processed.",
            "s3_path": s3_path,
            "file_id": file_id,
            "mongo_doc_id": mongo_doc_id,
            "claims_count": len(flat_claims),
            "claim_ids": claim_ids,
            "payer_template_status": payer_template_status
        })
    return {"success": "File Upload successfully."}
