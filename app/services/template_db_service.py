from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import uuid
import psycopg2
from pymongo import MongoClient
from ..services.pg_upload_files import get_pg_conn
from ..utils.logger import get_logger
from app.common.db.db import init_db

logger = get_logger(__name__)
DB = init_db() 

payer_ids = ''
def extract_and_save_payer_data(json_data: dict, org_id: str, filename: str = None) -> Optional[str]:
    """
    Extract payer information from template JSON data and save to payer table.
    
    Args:
        json_data: The extracted JSON data from template processing
        org_id: Organization ID
        filename: Optional filename to help extract payer information
        
    Returns:
        payer_id if created/found, None if no payer data found
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        # Common payer name fields to look for in JSON
        payer_name_fields = [
            'payer_name', 'payer', 'insurance_company', 'insurer', 'carrier',
            'insurance_carrier', 'plan_name', 'health_plan', 'insurance_plan',
            'company_name', 'organization_name', 'insurance_name'
        ]
        
        payer_name = None
        payer_code = None
        
        # Extract payer name from JSON data (case-insensitive search)
        for field in payer_name_fields:
            # Check exact match
            if field in json_data and json_data[field]:
                payer_name = str(json_data[field]).strip()
                break
            
            # Check case-insensitive match
            for key, value in json_data.items():
                if isinstance(key, str) and key.lower() == field.lower():
                    if value and str(value).strip():
                        payer_name = str(value).strip()
                        break
            
            if payer_name:
                break
        
        # If no direct payer name found, try to extract from nested structures
        if not payer_name:
            # Check claims array for payer information
            if 'claims' in json_data and isinstance(json_data['claims'], list):
                for claim in json_data['claims'][:3]:  # Check first 3 claims
                    if isinstance(claim, dict):
                        for field in payer_name_fields:
                            if field in claim and claim[field]:
                                payer_name = str(claim[field]).strip()
                                break
                        if payer_name:
                            break
            
            # Check payments array for payer information
            if not payer_name and 'payments' in json_data and isinstance(json_data['payments'], list):
                for payment in json_data['payments'][:3]:  # Check first 3 payments
                    if isinstance(payment, dict):
                        for field in payer_name_fields:
                            if field in payment and payment[field]:
                                payer_name = str(payment[field]).strip()
                                break
                        if payer_name:
                            break
            
            # Check raw_key_value_pairs for payer information
            if not payer_name and 'raw_key_value_pairs' in json_data:
                raw_data = json_data['raw_key_value_pairs']
                if isinstance(raw_data, dict):
                    for field in payer_name_fields:
                        if field in raw_data and raw_data[field]:
                            payer_name = str(raw_data[field]).strip()
                            break
        
        # Look for payer code fields
        payer_code_fields = ['payer_code', 'payer_id', 'plan_code', 'carrier_code', 'insurance_id']
        for field in payer_code_fields:
            if field in json_data and json_data[field]:
                payer_code = str(json_data[field]).strip()
                break
            
            # Check case-insensitive match
            for key, value in json_data.items():
                if isinstance(key, str) and key.lower() == field.lower():
                    if value and str(value).strip():
                        payer_code = str(value).strip()
                        break
            
            if payer_code:
                break
        
        # If no payer name found in JSON, try to extract from filename
        if not payer_name and filename:
            # Common payer names/patterns in filenames
            filename_payer_patterns = {
                'bcbs': 'Blue Cross Blue Shield',
                'bluecross': 'Blue Cross Blue Shield', 
                'blueshield': 'Blue Cross Blue Shield',
                'uhc': 'UnitedHealthcare',
                'united': 'UnitedHealthcare',
                'unitedhealthcare': 'UnitedHealthcare',
                'aetna': 'Aetna',
                'cigna': 'Cigna',
                'humana': 'Humana',
                'anthem': 'Anthem',
                'kaiser': 'Kaiser Permanente',
                'fallon': 'Fallon Health',
                'regence': 'Regence',
                'regenceblueshield': 'Regence BlueCross BlueShield'
            }
            
            filename_lower = filename.lower()
            for pattern, payer in filename_payer_patterns.items():
                if pattern in filename_lower:
                    payer_name = payer
                    logger.info(f"Extracted payer name from filename: {payer_name}")
                    break
        
        # If still no payer name found, return None
        if not payer_name:
            logger.info("No payer name found in template JSON data or filename")
            return None
        
        # Check if payer already exists
        cur.execute("""
            SELECT id FROM payers 
            WHERE org_id = %s AND (name = %s OR (payer_code IS NOT NULL AND payer_code = %s))
        """, (org_id, payer_name, payer_code))
        
        existing_payer = cur.fetchone()
        if existing_payer:
            logger.info(f"Payer already exists: {payer_name} (ID: {existing_payer[0]})")
            return str(existing_payer[0])
        
        # Create new payer
        payer_id = str(uuid.uuid4())
        created_by = "9f44298b-5e30-4a7c-a8cb-1ae003cd9134"  # Default user
        
        # Create AI detection metadata from the JSON data
        ai_detection_metadata = {
            "source": "template_json_extraction",
            "confidence": 85,
            "detected_fields": {
                "payer_name": payer_name,
                "payer_code": payer_code
            },
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "template_fields_used": [key for key in json_data.keys() if any(field in key.lower() for field in payer_name_fields + payer_code_fields)]
        }
        
        cur.execute("""
            INSERT INTO payers (
                id, org_id, name, payer_code, ai_detection_metadata, created_by, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            payer_id,
            org_id,
            payer_name,
            payer_code,
            json.dumps(ai_detection_metadata),
            created_by,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        conn.commit()
        logger.info(f"✅ Created new payer from template JSON: {payer_name} (ID: {payer_id})")
        return payer_id
        
    except Exception as e:
        logger.error(f"Error extracting/saving payer data: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

# MongoDB connection for template builder sessions
# def get_mongo_conn():
#     """Get MongoDB client connection for template builder sessions."""
#     try:
#         client = MongoClient("mongodb://localhost:27017/")
#         return client
#     except Exception as e:
#         logger.error(f"Failed to connect to MongoDB: {e}")
#         raise

def create_template_in_postgres(
    name: str,
    filename: str,
    # template_path: str,
    org_id: str = "9ac493f7-cc6a-4d7d-8646-affb00ed58da",
    payer_id: str = payer_ids,  # Default payer_id
    template_type: str = "other",
    template_path: str = None,
    
) -> str:
    """
    Create a new template record in the templates table.
    
    Returns template_id
    """
    
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        template_id = str(uuid.uuid4())
        created_by = "9f44298b-5e30-4a7c-a8cb-1ae003cd9134"  # Default user
        
        cur.execute("""
            INSERT INTO templates (
                id, name, type, status, org_id, payer_id, created_by, created_at, updated_at, template_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            template_id,
            name,
            template_type,
            "active",
            org_id,
            payer_id,
            created_by,
            datetime.utcnow(),
            datetime.utcnow(),
            template_path
        ))
        
        conn.commit()
        logger.info(f"✅ Created template in PostgreSQL: {template_id}")
        return template_id
        
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def create_template_version(
    template_id: str,
    dynamic_keys: List[str],
    mongo_doc_id: str,
    ai_model_name: str = "gpt-4o-mini",
    notes: str = "Auto-generated from file upload"
) -> str:
    """
    Create a new template version in the template_versions table.
    
    Returns version_id
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        version_id = str(uuid.uuid4())
        created_by = "9f44298b-5e30-4a7c-a8cb-1ae003cd9134"  # Default user
        
        # Get next version number
        cur.execute("""
            SELECT COALESCE(MAX(version_number), 0) + 1 
            FROM template_versions 
            WHERE template_id = %s
        """, (template_id,))
        
        version_number = cur.fetchone()[0]
        
        # Extract flat key names from sections structure for notes
        flat_key_names = []
        if isinstance(dynamic_keys, list) and len(dynamic_keys) > 0:
            if isinstance(dynamic_keys[0], dict):  # Section-based format
                for section in dynamic_keys:
                    if isinstance(section, dict) and "fields" in section:
                        for field in section.get("fields", []):
                            if isinstance(field, dict) and "field" in field:
                                flat_key_names.append(field["field"])
            else:  # Legacy flat list format
                flat_key_names = [str(k) for k in dynamic_keys if k]
        
        keys_str = ', '.join(flat_key_names[:10]) if flat_key_names else "none"
        
        cur.execute("""
            INSERT INTO template_versions (
                id, template_id, version_number, status, ai_generated, ai_model_name, mongo_doc_id, notes, created_by, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            version_id,
            template_id,
            version_number,
            "active",
            True,
            ai_model_name,
            mongo_doc_id,
            f"{notes}. Dynamic keys: {keys_str}",
            created_by,
            datetime.utcnow()
        ))
        
        # Update template to point to this version
        cur.execute("""
            UPDATE templates 
            SET current_version_id = %s, updated_at = %s
            WHERE id = %s
        """, (version_id, datetime.utcnow(), template_id))
        
        conn.commit()
        logger.info(f"✅ Created template version: {version_id} (v{version_number})")
        return version_id
        
    except Exception as e:
        logger.error(f"Error creating template version: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def save_template_data(
    template_id: str,
    filename: str,
    raw_text: str,
    json_data: dict,
    dynamic_keys: List[str],
    file_size: int,
    mime_type: str,
    ai_confidence: int = 85,
) -> dict:
    """Save template processing results to database using existing schema."""
    
    # Generate MongoDB document ID first
    mongo_doc_id = str(uuid.uuid4())
    
    # Save session data to MongoDB first
    # mongo_client = get_mongo_conn()
    # db = mongo_client['eob_db']

    sessions_collection = DB['template_builder_sessions']
    
    try:
        session_data = {
            "_id": mongo_doc_id,
            "template_id": template_id,
            "filename": filename,
            "raw_text": raw_text[:10000],  # Limit size for MongoDB
            "extracted_data": json_data,
            "dynamic_keys": dynamic_keys,
            "ai_confidence": ai_confidence,
            "file_metadata": {
                "size": file_size,
                "mime_type": mime_type,
                "processing_method": "ai_dynamic_extraction"
            },
            "status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert session data
        sessions_collection.insert_one(session_data)
        
        # Create template version with mongo doc reference
        version_id = create_template_version(
            template_id=template_id,
            dynamic_keys=dynamic_keys,
            mongo_doc_id=mongo_doc_id,
            ai_model_name="gpt-4o-mini",
            notes=f"Generated from {filename}"
        )
        
        # Update session data with version_id
        sessions_collection.update_one(
            {"_id": mongo_doc_id},
            {"$set": {"version_id": version_id}}
        )
        
        result = {
            "template_id": template_id,
            "version_id": version_id,
            "session_id": mongo_doc_id,
            "filename": filename,
            "dynamic_keys": dynamic_keys,
            "ai_confidence": ai_confidence,
            "records_created": 2
        }
        
        logger.info(f"✅ Saved template data using existing schema: {result}")
        
        # Extract and save payer data from template JSON
        extract_and_save_payer_data(json_data, org_id="9ac493f7-cc6a-4d7d-8646-affb00ed58da", filename=filename)
        
        return result
        
    except Exception as e:
        logger.error(f"Error saving template data: {e}")
        raise
    finally:
        logger.info("Closing MongoDB connection")
        # mongo_client.close()

def process_existing_templates_for_payer_data(org_id: str = "9ac493f7-cc6a-4d7d-8646-affb00ed58da") -> Dict[str, Any]:
    """
    Process all existing template JSON data to extract and save payer information.
    
    Args:
        org_id: Organization ID to process templates for
        
    Returns:
        Dictionary with processing results
    """
    # mongo_client = get_mongo_conn()
    # db = mongo_client['eob_db']
    sessions_collection = DB['template_builder_sessions']
    
    results = {
        "processed_templates": 0,
        "payers_created": 0,
        "payers_found_existing": 0,
        "templates_without_payer_data": 0,
        "errors": []
    }
    
    try:
        # Get all template sessions with extracted data
        sessions = sessions_collection.find({
            "status": "completed",
            "extracted_data": {"$exists": True, "$ne": None}
        })
        
        for session in sessions:
            results["processed_templates"] += 1
            
            try:
                extracted_data = session.get("extracted_data", {})
                if not extracted_data:
                    results["templates_without_payer_data"] += 1
                    continue
                
                session_filename = session.get("filename", "")
                payer_id = extract_and_save_payer_data(extracted_data, org_id, session_filename)
                
                if payer_id:
                    # Check if this is a new payer or existing
                    conn = get_pg_conn()
                    cur = conn.cursor()
                    cur.execute("SELECT created_at FROM payers WHERE id = %s", (payer_id,))
                    payer_data = cur.fetchone()
                    cur.close()
                    conn.close()
                    
                    # If created recently (within last minute), it's new
                    if payer_data:
                        # Handle timezone-aware vs naive datetime comparison
                        created_at = payer_data[0]
                        if created_at.tzinfo is not None:
                            from datetime import timezone
                            now = datetime.now(timezone.utc)
                        else:
                            now = datetime.utcnow()
                        
                        if (now - created_at).total_seconds() < 60:
                            results["payers_created"] += 1
                        else:
                            results["payers_found_existing"] += 1
                else:
                    results["templates_without_payer_data"] += 1
                    
            except Exception as e:
                error_msg = f"Error processing template {session.get('_id', 'unknown')}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"✅ Processed {results['processed_templates']} templates for payer data extraction")
        return results
        
    except Exception as e:
        logger.error(f"Error processing existing templates: {e}")
        results["errors"].append(str(e))
        return results
    finally:
        logger.info("Closing MongoDB connection")
        # mongo_client.close()

def get_template_by_id(template_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve complete template data by ID using existing schema."""
    conn = None
    cur = None
    # mongo_client = None
    
    try:
        # Get template data from PostgreSQL
        conn = get_pg_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                t.id, t.name, t.type, t.status, t.org_id, t.payer_id, t.created_at,
                tv.id as version_id, tv.version_number, tv.ai_model_name, tv.notes
            FROM templates t
            LEFT JOIN template_versions tv ON t.current_version_id = tv.id
            WHERE t.id = %s
        """, (template_id,))
        
        template_data = cur.fetchone()
        if not template_data:
            return None
        
        # Get session data from MongoDB
        # mongo_client = get_mongo_conn()
        # db = mongo_client['eob_db']
        sessions_collection = DB['template_builder_sessions']
        
        session_data = sessions_collection.find_one({"template_id": template_id})
        
        result = {
            "template_id": str(template_data[0]),
            "name": template_data[1],
            "type": template_data[2],
            "status": template_data[3],
            "org_id": str(template_data[4]),
            "payer_id": str(template_data[5]) if template_data[5] else None,
            "created_at": template_data[6].isoformat() if template_data[6] else None,
            "current_version": {
                "id": str(template_data[7]) if template_data[7] else None,
                "version_number": template_data[8],
                "ai_model_name": template_data[9],
                "notes": template_data[10]
            } if template_data[7] else None
        }
        
        if session_data:
            result["session_data"] = {
                "session_id": str(session_data["_id"]),
                "filename": session_data.get("filename"),
                "extracted_data": session_data.get("extracted_data"),
                "dynamic_keys": session_data.get("dynamic_keys", []),
                "ai_confidence": session_data.get("ai_confidence"),
                "file_metadata": session_data.get("file_metadata"),
                "status": session_data.get("status"),
                "created_at": session_data["created_at"].isoformat() if session_data.get("created_at") else None
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving template: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        # if mongo_client:
        #     mongo_client.close()
        logger.info("Closed DB connection")

def list_all_templates(limit: int = 50) -> List[Dict[str, Any]]:
    """List all templates with basic information using existing schema."""
    conn = None
    cur = None
    # mongo_client = None
    
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                t.id, t.name, t.type, t.status, t.created_at,
                tv.version_number, tv.ai_model_name
            FROM templates t
            LEFT JOIN template_versions tv ON t.current_version_id = tv.id
            ORDER BY t.created_at DESC
            LIMIT %s
        """, (limit,))
        
        templates = []
        
        # Get MongoDB connection for session data
        # mongo_client = get_mongo_conn()
        # db = mongo_client['eob_db']
        sessions_collection = DB['template_builder_sessions']
        
        for row in cur.fetchall():
            template_id = str(row[0])
            
            # Get session data for additional info
            session_data = sessions_collection.find_one({"template_id": template_id})
            
            template_info = {
                "template_id": template_id,
                "name": row[1],
                "type": row[2],
                "status": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "current_version": row[5],
                "ai_model": row[6]
            }
            
            if session_data:
                template_info.update({
                    "filename": session_data.get("filename"),
                    "ai_confidence": session_data.get("ai_confidence"),
                    "dynamic_keys_count": len(session_data.get("dynamic_keys", [])),
                    "file_size": session_data.get("file_metadata", {}).get("size"),
                    "mime_type": session_data.get("file_metadata", {}).get("mime_type")
                })
            
            templates.append(template_info)
        
        return templates
        
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        # if mongo_client:
        #     mongo_client.close()
        logger.info("Closed DB connection")

def get_template_keys_by_id(template_id: str) -> List[str]:
    """Get the dynamic keys for a specific template using existing schema."""
    # mongo_client = None
    
    try:
        # mongo_client = get_mongo_conn()
        # db = mongo_client['eob_db']
        sessions_collection = DB['template_builder_sessions']
        
        session_data = sessions_collection.find_one({"template_id": template_id})
        return session_data.get("dynamic_keys", []) if session_data else []
        
    except Exception as e:
        logger.error(f"Error getting template keys: {e}")
        return []
    finally:
        # if mongo_client:
        #     mongo_client.close()
        logger.info("Closed DB connection")

def update_template_session_data(
    template_id: str,
    updated_data: Dict[str, Any],
    confidence: int = None
) -> bool:
    """Update existing template session data in MongoDB."""
    # mongo_client = None
    
    try:
        # mongo_client = get_mongo_conn()
        # db = mongo_client['eob_db']
        sessions_collection = DB['template_builder_sessions']
        
        update_doc = {
            "extracted_data": updated_data,
            "updated_at": datetime.utcnow()
        }
        
        if confidence is not None:
            update_doc["ai_confidence"] = confidence
        
        result = sessions_collection.update_one(
            {"template_id": template_id},
            {"$set": update_doc}
        )
        
        success = result.modified_count > 0
        
        if success:
            logger.info(f"✅ Updated template session data: {template_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error updating template session data: {e}")
        return False
    finally:
        # if mongo_client:
        #     mongo_client.close()
        logger.info("Closed DB connection")