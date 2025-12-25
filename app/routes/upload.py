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
from app.common.db.pg_db import get_pg_conn
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
from ..services.auth_deps import get_current_user, require_role


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
async def upload_files(user: Dict[str, Any] = Depends(get_current_user), files: List[UploadFile] = File(...)) -> Dict[str, Any]:

    """
    Upload one or more files, validate size, corruption, hash, and format.
    Returns status and message per file.
    """
    user_id = user.get("id")
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute("""SELECT org_id, role FROM organization_memberships WHERE user_id = %s LIMIT 1
                """, (user_id,))
    membership = cur.fetchone()
    org_id = membership[0]
    responses = []
    ext_collection = db_module.db["extraction_results"]  
    claim_version = db_module.db["claim_version"]  
    for file in files:
        try:
            content = await file.read()
        except Exception:
            raise HTTPException(status_code=400, detail={"filename": file.filename, "status": "error", "message": "File is corrupted"})
        # 1. Check file size
        file_hash = calculate_file_hash(content)
 
        if check_hash_exists(file_hash):
            raise HTTPException(
                status_code=400,
                detail=f"This file is already uploaded: {file.filename}"
            )
        
        if file.size and file.size > MAX_FILE_SIZE:
            responses.append({"filename": file.filename, "status": "error", "message": "File too large (max 50MB)"})
            continue
        
        if len(content) > MAX_FILE_SIZE:
            responses.append({"filename": file.filename, "status": "error", "message": "File too large (max 50MB)"})
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
   
        batch_id = None
        mime_type = file.content_type or "application/octet-stream"
        logger.info(f"Processing file: {file.filename}, size: {len(content)}, mime_type: {mime_type}")
        file_size = len(content)
        upload_source = "manual"
        
        uploaded_by = user_id

        
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
            status="ai_processing"  # Set status to "Pending Review" on first upload
        )
        
        return {"success": "File Upload successfully."}

