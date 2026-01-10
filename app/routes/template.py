from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from typing import Dict, Any, List
import json
import uuid
from datetime import datetime
import hashlib
import tempfile

from ..utils.logger import get_logger
from ..services.file_text_extractor import extract_text_from_file
from ..services.pg_upload_files import insert_upload_file, get_pg_conn, update_file_status, mark_processing_failed
from ..services.s3_service import S3Service
from ..common.config import settings
from ..services.ai_template_processor import process_template_with_dynamic_extraction
from ..services.template_db_service import (
    create_template_in_postgres,
    save_template_data,
    get_template_by_id,
    list_all_templates,
    get_template_keys_by_id
)
from ..services.file_type_handler import (
    detect_file_type,
    validate_file_content, 
    get_processing_strategy,
    clean_extracted_text,
    SUPPORTED_MIME_TYPES
)
from app.services.template_db_service import get_pg_conn
from pymongo import MongoClient
import os
from app.common.db.db import init_db
from ..services.auth_deps import get_current_user, require_role
from ..services.template_text_extractor import extract_raw_text 


DB = init_db() 
logger = get_logger(__name__)

router = APIRouter(prefix="/template", tags=["template"])


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_template_file(user: Dict[str, Any] = Depends(get_current_user), file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Upload ANY type of template file, extract text, dynamically identify keys, and convert to JSON using AI.
    
    Supports: PDF, DOCX, DOC, XLSX, XLS, TXT, CSV, Images (JPG, PNG, etc.), JSON, XML, and more!
    
    Process:
    1. Detect and validate file type
    2. Extract text using appropriate method
    3. Save raw text data in database
    4. Use AI to identify dynamic keys from the text
    5. Convert text to JSON using only keys found in the text
    6. Save JSON data in database
    """
    try:
        user_id = user.get("id")
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""SELECT org_id, role FROM organization_memberships WHERE user_id = %s LIMIT 1
                    """, (user_id,))
        membership = cur.fetchone()
        org_id = membership[0]  
        # 1. Read and validate file content
        content = await file.read()
        # Upload file to S3
        s3_service = S3Service(
            bucket_name=settings.S3_BUCKET,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        s3_key = f"templates/{file.filename}"
        try:
            # s3_service.upload_file(file_content=content, file_name=s3_key)
            s3_path = s3_service.upload_file(content, s3_key)

            logger.info(f"Uploaded file to S3: {s3_key}")
        except Exception as s3e:
            logger.error(f"Failed to upload file to S3: {s3e}")
            raise HTTPException(status_code=500, detail="Failed to upload file to S3")

        # Basic file validation
        is_valid, validation_error = validate_file_content(content, file.filename)
        if not is_valid:
            logger.error(f"File validation failed for {file.filename}: {validation_error}")
            raise HTTPException(status_code=400, detail=validation_error)

        # 2. Detect file type using multiple methods
        detected_mime_type, file_extension, is_supported = detect_file_type(content, file.filename)
        
        if not is_supported:
            supported_types = list(SUPPORTED_MIME_TYPES.keys())
            logger.warning(f"Unsupported file type {detected_mime_type} for {file.filename}")
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {detected_mime_type}. Supported types: {', '.join(supported_types[:10])}..."
            )

        # 3. Get processing strategy for this file type
        processing_strategy = get_processing_strategy(detected_mime_type, file_extension)
        
        logger.info(f"Processing {file.filename} as {file_extension} ({detected_mime_type}) using {processing_strategy['method']}")

        # 4. Extract text using the appropriate method
        raw_text = extract_raw_text(
            filename=file.filename,
            content_type=detected_mime_type,
            content=content
        )
        
        extraction_result = await process_template_with_dynamic_extraction(raw_text)
        dynamic_keys = extraction_result.get("dynamic_keys", [])
        
        payer_name = dynamic_keys.get("payerName")
        cur.execute("""
            SELECT id
            FROM templates
            WHERE name = %s
            ORDER BY id DESC
            LIMIT 1
        """, (payer_name,))
        template_row = cur.fetchone()   
        if template_row:
            template_id = str(template_row[0])
        
            cur.execute("""
                SELECT template_json
                FROM template_versions
                WHERE template_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (template_id,))
            
            version_row = cur.fetchone()
            
            if version_row:
                template_json = version_row[0]
                if isinstance(template_json, str):
                    template_json = json.loads(template_json)
                
                existing_fields = set()
                if isinstance(template_json, dict):
                    sections = template_json.get("sections", [])
                elif isinstance(template_json, list):
                    sections = template_json
                else:
                    sections = []
                
                for section in sections:
                    if isinstance(section, dict):
                        for field in section.get("fields", []):
                            if isinstance(field, dict) and "field" in field:
                                existing_fields.add(field["field"])
                
                # STEP 6: Extract all field values from dynamic_keys.sections
                incoming_fields = set()
                incoming_sections = dynamic_keys.get("sections", [])
                
                for section in incoming_sections:
                    if isinstance(section, dict):
                        for field in section.get("fields", []):
                            if isinstance(field, dict) and "field" in field:
                                incoming_fields.add(field["field"])
                
                # STEP 7: Compare fields - Match requires ALL fields from dynamic_keys to exist in template_json
                print("incoming_fields========", incoming_fields)
                print("existing_fields========", existing_fields)
                if incoming_fields and incoming_fields.issubset(existing_fields):
                    # ALL conditions matched
                    return {
                        "status": "template already exist",
                    }

        # Extract payer_id dynamically from JSON and create template in PostgreSQL
        payer_name = dynamic_keys.get("payerName", "UnknownPayer") 
        from app.services.template_db_service import extract_and_save_payer_data
        
        payer_id = extract_and_save_payer_data(dynamic_keys, org_id, file.filename, payer_name, user_id)
        if not payer_id:
            # Fallback: create/get 'Unknown Payer' for org
            from app.services.payer_template_service import get_or_create_payer
            payer_id = get_or_create_payer('Unknown Payer', org_id)
        template_name = f"Template-{file.filename}-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        template_id = create_template_in_postgres(
            name=payer_name,
            filename=file.filename,
            org_id=org_id,
            payer_id=payer_id,
            template_type="other",
            template_path=s3_path
            
        )
        
        # 8. Save complete template data using existing schema
        save_result = save_template_data(
            template_id=template_id,
            filename=file.filename,
            raw_text=raw_text,
            json_data=dynamic_keys,
            dynamic_keys=dynamic_keys,
            file_size=len(content),
            mime_type=detected_mime_type,
            user_id=user_id,
            ai_confidence=85
            
        )
        
        return {
            "template_id": template_id,
            "version_id": save_result["version_id"],
            "session_id": save_result["session_id"],
            "filename": file.filename,
            "file_info": {
                "type": file_extension,
                "mime_type": detected_mime_type,
                "size_bytes": len(content),
                "processing_method": processing_strategy['method'],
                "expected_confidence": processing_strategy['confidence']
            },
            "raw_text_length": len(raw_text),
            "dynamic_keys_found": len(dynamic_keys),
            "dynamic_keys": dynamic_keys,
            "records_created": save_result["records_created"],
            "file_path": s3_path,
            "message": f"Template processed successfully as {file_extension} file using {processing_strategy['method']} and saved to existing database schema"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing template file: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to process template file: {str(e)}"
        )

# @router.get("/templates/{template_id}")
# async def get_template(template_id: str) -> Dict[str, Any]:
    # """Get template data by ID."""
    # try:
    #     template_data = get_template_by_id(template_id)
    #     if not template_data:
    #         raise HTTPException(status_code=404, detail="Template not found")
        
    #     return template_data
    # except HTTPException:
    #     raise
    # except Exception as e:
    #     logger.error(f"Error retrieving template: {str(e)}")
    #     raise HTTPException(status_code=500, detail="Failed to retrieve template")

@router.get("/templates")
async def list_templates() -> Dict[str, Any]:
    """List all templates."""
    try:
        from ..services.template_db_service import list_all_templates
        templates = list_all_templates()
        return {"templates": templates, "count": len(templates)}
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list templates")
    
    
@router.get("/template-listing", status_code=status.HTTP_200_OK)
async def get_template_listing(
    user: Dict[str, Any] = Depends(get_current_user),
    search: str = None,
    page: int = 1,
    page_size: int = 10
) -> Dict[str, Any]:
    try:
        # Connect to Postgres
        conn = get_pg_conn()
        cur = conn.cursor()

        user_id = user.get("id")
        cur.execute("""SELECT org_id, role FROM organization_memberships WHERE user_id = %s LIMIT 1
                    """, (user_id,))
        membership = cur.fetchone()
        org_id = membership[0]

        # Connect to MongoDB using init_db from db.py
        
        builder_collection = DB["template_builder_sessions"]

        # 1. Get all templates for the org with optional search filter
        if search:
            cur.execute("""
                SELECT t.id, t.name, t.status, t.updated_at
                FROM templates t
                WHERE t.org_id = %s AND t.name ILIKE %s
                ORDER BY t.id DESC
            """, (org_id, f"%{search}%"))
        else:
            cur.execute("""
                SELECT t.id, t.name, t.status, t.updated_at
                FROM templates t
                WHERE t.org_id = %s 
                ORDER BY t.id DESC
            """, (org_id,))
        templates = cur.fetchall()
        result = []
        for template_id, template_name, status, updated_at in templates:
            # 2. Get latest version for this template
            cur.execute("""
                SELECT version_number FROM template_versions
                WHERE template_id = %s
                ORDER BY created_at DESC LIMIT 1
            """, (template_id,))
            version_row = cur.fetchone()
            version = version_row[0] if version_row else 0
            # 3. Get field mapping info and usage count from MongoDB (async)
            builder_doc = await builder_collection.find_one({"template_id": str(template_id)})
            total_field = builder_doc.get("total_field") if builder_doc else None
            mapping_field = builder_doc.get("mapped_field") if builder_doc else None
            usage_count = await builder_collection.count_documents({"template_id": str(template_id)})

            result.append({
                "template_id": template_id,
                "template_name": template_name,
                "version": version,
                "field_mapped": f"{mapping_field}/{total_field}" if mapping_field is not None and total_field is not None else "",
                "usage_count": usage_count,
                "status": status,
                "updated_at": str(updated_at) if updated_at else None,
            })
        
        # Apply pagination
        total_records = len(result)
        total_pages = (total_records + page_size - 1) // page_size
        if page > total_pages and total_pages > 0:
            page = total_pages
        start = (page - 1) * page_size
        end = start + page_size
        paginated_result = result[start:end]
        
        cur.close()
        conn.close()
        return {
            "message": "templates retrieved successfully", 
            "templates": paginated_result,
            "pagination": {
                "total": total_records,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        }
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list templates")
    