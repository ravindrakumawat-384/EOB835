from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from typing import Dict, Any, List
import json
import uuid
from datetime import datetime
import hashlib

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


DB = init_db() 
logger = get_logger(__name__)

router = APIRouter(prefix="/template", tags=["template"])


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_template_file(file: UploadFile = File(...)) -> Dict[str, Any]:
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
            s3_service.upload_file(file_content=content, file_name=s3_key)
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
        raw_text = extract_text_from_file(content, file.filename, detected_mime_type)

        if not raw_text or len(raw_text.strip()) < 10:
            raise HTTPException(
                status_code=400, 
                detail=f"Could not extract meaningful text from {file_extension} file. Processing method: {processing_strategy['method']}"
            )
        print('raw_text=========', raw_text)
        # 5. Clean extracted text based on processing method
        cleaned_text = clean_extracted_text(raw_text, processing_strategy['method'])
        print('cleaned_text=========', cleaned_text)
        if not cleaned_text or len(cleaned_text.strip()) < 10:
            raise HTTPException(
                status_code=400, 
                detail="Text contains too many corrupted characters after cleaning"
            )

        logger.info(f"Extracted and cleaned text (first 200 chars): {cleaned_text[:200]}")
        
        # 6. Use AI to dynamically extract keys and convert to JSON
        logger.info(f"🤖 Processing {file_extension} file with dynamic extraction using AI...")
        
        # Final validation before AI processing
        try:
            # Test if the text can be safely encoded/decoded
            test_json = json.dumps({"test": cleaned_text[:5000]})
            logger.info("Text validation passed for AI processing")
        except (UnicodeDecodeError, UnicodeEncodeError, ValueError) as e:
            logger.error(f"Text encoding validation failed: {e}")
            raise HTTPException(
                status_code=400,
                detail="Text contains invalid characters that cannot be processed"
            )
        
        extraction_result = await process_template_with_dynamic_extraction(cleaned_text, file.filename)
        
        dynamic_keys = extraction_result.get("dynamic_keys", [])
        json_result = extraction_result.get("extraction_data", {})
        
        # 7. Extract payer_id dynamically from JSON and create template in PostgreSQL
        # 7. Extract payer_name from JSON and use as template name
        payer_name = None
        payer_fields = [
            "payer_name", "payer", "insurance_company", "insurer", "carrier",
            "insurance_carrier", "plan_name", "health_plan", "insurance_plan",
            "company_name", "organization_name", "insurance_name"
        ]
        # 1. Check top-level fields
        for field in payer_fields:
            val = json_result.get(field)
            if val:
                payer_name = str(val).strip()
                break
        # 2. Check payer_info object
        if not payer_name and "payer_info" in json_result:
            payer_info = json_result["payer_info"]
            if isinstance(payer_info, dict):
                for field in payer_fields:
                    val = payer_info.get(field)
                    if val:
                        payer_name = str(val).strip()
                        break
        # 3. Check claims
        if not payer_name:
            claims = json_result.get("claims", [])
            if claims and isinstance(claims, list):
                for claim in claims:
                    for field in payer_fields:
                        val = claim.get(field)
                        if val:
                            payer_name = str(val).strip()
                            break
                    if payer_name:
                        break
        if not payer_name:
            payer_name = "UnknownPayer"
        # Extract payer_id dynamically from JSON and create template in PostgreSQL
        from app.services.template_db_service import extract_and_save_payer_data
        org_id = "9ac493f7-cc6a-4d7d-8646-affb00ed58da"
        payer_id = extract_and_save_payer_data(json_result, org_id, file.filename)
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
            template_path=s3_key
            
        )
        
        # 8. Save complete template data using existing schema
        save_result = save_template_data(
            template_id=template_id,
            filename=file.filename,
            raw_text=cleaned_text,
            json_data=json_result,
            dynamic_keys=dynamic_keys,
            file_size=len(content),
            mime_type=detected_mime_type,
            ai_confidence=json_result.get("extraction_confidence", 85)
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
            "raw_text_length": len(cleaned_text),
            "dynamic_keys_found": len(dynamic_keys),
            "dynamic_keys": dynamic_keys,
            "json_data": json_result,
            "ai_confidence": json_result.get("extraction_confidence", 85),
            "records_created": save_result["records_created"],
            "file_path": s3_key,
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

@router.get("/supported-types", status_code=status.HTTP_200_OK)
async def get_supported_file_types() -> Dict[str, Any]:
    """
    Get all supported file types for template processing.
    """
    return {
        "supported_file_types": SUPPORTED_MIME_TYPES,
        "total_types": len(SUPPORTED_MIME_TYPES),
        "categories": {
            "text_files": ["TXT", "CSV", "TSV", "JSON", "XML"],
            "office_documents": ["PDF", "DOCX", "DOC", "XLSX", "XLS", "PPTX", "PPT", "ODT", "ODS"],
            "images": ["JPG", "PNG", "GIF", "BMP", "TIFF", "WEBP"],
            "archives": ["ZIP", "RAR", "7Z"],
            "other": ["RTF", "EML", "MSG"]
        },
        "processing_methods": {
            "direct_text": "Plain text files - highest accuracy",
            "structured_text": "CSV, TSV files - preserves data structure", 
            "structured_data": "JSON, XML files - direct data extraction",
            "pdf_extraction": "PDF files - text and image extraction",
            "office_extraction": "Microsoft Office documents",
            "spreadsheet_extraction": "Excel files with table data",
            "ocr_extraction": "Image files using OCR technology",
            "fallback_extraction": "Other file types - best effort"
        }
    }

@router.get("/templates/{template_id}")
async def get_template(template_id: str) -> Dict[str, Any]:
    """Get template data by ID."""
    try:
        template_data = get_template_by_id(template_id)
        if not template_data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return template_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving template: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve template")

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
async def get_template_listing(org_id: str) -> Dict[str, Any]:
    try:
        # Connect to Postgres
        conn = get_pg_conn()
        cur = conn.cursor()

        # Connect to MongoDB using init_db from db.py
        
        builder_collection = DB["template_builder_sessions"]

        # 1. Get all templates for the org
        cur.execute("""
            SELECT t.id, t.name
            FROM templates t
            WHERE t.org_id = %s
        """, (org_id,))
        templates = cur.fetchall()

        result = []
        for template_id, template_name in templates:
            # 2. Get latest version for this template
            cur.execute("""
                SELECT version_number FROM template_versions
                WHERE template_id = %s
                ORDER BY created_at DESC LIMIT 1
            """, (template_id,))
            version_row = cur.fetchone()
            version = version_row[0] if version_row else 0
            print('template_id=====', template_id)
            # 3. Get field mapping info and usage count from MongoDB (async)
            builder_doc = await builder_collection.find_one({"template_id": str(template_id)})
            total_field = builder_doc.get("total_field") if builder_doc else None
            mapping_field = builder_doc.get("mapped_field") if builder_doc else None
            usage_count = await builder_collection.count_documents({"template_id": str(template_id)})

            # if not builder_doc.get("dynamic_keys"):
            #     return 0

            # total_fields = sum(
            #     len(section.get("fields", []))
            #     for section in builder_doc.get("dynamic_keys", [])
            #     if isinstance(section, dict)
            # )


            result.append({
                "template_id": template_id,
                "template_name": template_name,
                "version": version,
                "field_mapped ": f"{mapping_field}/{total_field}",
                "usage_count": usage_count
            })
        cur.close()
        conn.close()
        return {"message": "templates retrieved successfully", "templates": result}
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list templates")
    

@router.post("/update-template-version", status_code=status.HTTP_200_OK)
def update_template_version(template_id: str, template_json: dict, template_info: dict) -> Dict[str, Any]:
    try:
        pass
        
    except Exception as e:
        logger.error(f"Error retrieving template version: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve template version")