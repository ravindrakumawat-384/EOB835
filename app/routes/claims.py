from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
import psycopg2
import json
from app.common.db.db import init_db
from ..utils.logger import get_logger
# from ..services.pg_upload_files import get_pg_conn
from app.common.db.pg_db import get_pg_conn
from app.services.s3_service import S3Service
from app.common.config import settings
from datetime import datetime, timezone
from pymongo import ReturnDocument
from typing import Dict, Any
from ..services.auth_deps import get_current_user, require_role

DB = init_db()
logger = get_logger(__name__) 

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("/claim_details")
async def get_claims_detail(claim_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get the claim details with the given claim ID and database uses for this mongodb and PostgreSQL.
    upload file table to get the S3 storage path.
    mongoDB to get the claim data
    """
    try:
        user_id = user.get("id")
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""SELECT org_id, role FROM organization_memberships WHERE user_id = %s LIMIT 1
                    """, (user_id,))
        membership = cur.fetchone()
        org_id = membership[0]
        extraction_claims = DB["claim_version"]
        extraction_results = DB["extraction_results"]
        query = {
            
            "extraction_id": claim_id
        }
        result = await extraction_claims.find_one(query, sort=[("created_at", 1)])
        
        if not result:
            raise HTTPException(status_code=404, detail="Claim not found")

        claim_data = result.get('claim', {})
        file_id = result.get('file_id', '')
 
        extraction_result = await extraction_results.find_one({"_id": claim_id})
        claim_number = extraction_result.get('claimNumber', '')
        status = extraction_result.get('status', '')    
        
        # Ensure file_id is a string, not a dict
        if isinstance(file_id, dict):
            file_id = str(file_id.get('$oid', '')) if '$oid' in file_id else str(file_id)
        
        conn = get_pg_conn()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, storage_path, original_filename
            FROM upload_files
            WHERE id = %s
            """,
            (str(file_id),)
        )

        result = cur.fetchone()
        file_id = result[0]
        storage_path = result[1] if result else None
        file_name = result[2] if result else None   
        
        cur.close()
        conn.close()
        
        # Generate presigned URL for S3 file access
        presigned_url = None
        if storage_path:
            try:
                # Initialize S3 service
                s3_service = S3Service(
                    settings.S3_BUCKET,
                    settings.AWS_ACCESS_KEY_ID,
                    settings.AWS_SECRET_ACCESS_KEY,
                    settings.AWS_REGION
                )
                
                # Generate presigned URL (valid for 5 minutes for better security)
                presigned_url = s3_service.generate_presigned_url(storage_path, expiration=300)
                
            except Exception as s3_error:
                logger.error(f"Error generating presigned URL: {str(s3_error)}")
        
        return {"status": 200,
                "message": "Claims retrieved successfully", 
                "file_id": file_id,
                "file_name": file_name,
                "claim_number": claim_number,
                "status_claim": status,
                "file_location": presigned_url,
                "claim": claim_data,
                "result": result
                }
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail="Something went wrong while fetching claim details.")

def flatten_updates(data: Any, out: Dict[str, Any]):
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                flatten_updates(v, out)
            else:
                out[k] = v
    elif isinstance(data, list):
        for item in data:
            flatten_updates(item, out)


def apply_user_updates(claim: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts ANY JSON shape.
    Extracts all leaf keys and updates matching claim.fields[].field values.
    """

    if not claim or not updates:
        return claim

    flat_updates: Dict[str, Any] = {}
    flatten_updates(updates, flat_updates)

    for section in claim.get("sections", []):
        for field_obj in section.get("fields", []):
            field_key = field_obj.get("field")
            if field_key in flat_updates:
                field_obj["value"] = flat_updates[field_key]

    return claim


@router.post("")
async def save_claims_data(claim_json: Dict[str, Any], file_id: str, claim_id: str, check: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        version_collection = DB["claim_version"]
        extraction_collection = DB["extraction_results"]
        updated_by = user.get("id")
        query = {
            "extraction_id": claim_id
        }
        result = await version_collection.find_one(query, sort=[("created_at", 1)])
        
        # Get latest version for version calculation
        latest_version_doc = await version_collection.find_one(
            {"extraction_id": claim_id},
            sort=[("version", -1)]
        )
        
        next_version = "1.0"
        if latest_version_doc:
            current_version = latest_version_doc.get("version", "1.0")
            # Split version into major and minor parts
            version_parts = current_version.split(".")
            major = int(version_parts[0])
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            # Increment minor version
            minor += 1
            next_version = f"{major}.{minor}"

        if check == "exception" and result.get("status") != "approved":
            # Update extraction status to 'exception' in extraction_results collection
            await extraction_collection.update_one(
                {"_id": claim_id},
                {"$set": {"status": "exception"}}
            )

            await version_collection.update_one(
                {"extraction_id": claim_id},
                {"$set": {"status": "exception"}}
            )
            return {"message": "Claim marked as exception successfully.", "status": 200}  
         
        # Handle draft case

        elif check == "draft" and result.get("status") != "approved" and result.get("status") != "exception":
            # Insert new version record
            await version_collection.insert_one({
                "file_id": file_id,
                "extraction_id": claim_id,
                "version": next_version,
                "claim": claim_json,
                "created_at": datetime.now(timezone.utc),
                "updated_by": updated_by,
                "status": "preview_pending"
            })
            result = await version_collection.find_one(query, sort=[("created_at", 1)])
            predefined_json = result.get("claim", {})
            # ---------- apply user updates ----------
            updated_claim = apply_user_updates(predefined_json, claim_json)

            # ---------- version calculation ----------
            await version_collection.find_one_and_update(
                {"extraction_id": claim_id},
                {
                    "$set": {
                        "claim": updated_claim,
                        "updated_at": datetime.now(timezone.utc)
                    }
                },
                sort=[("created_at", 1)],   # first record (earliest)
                return_document=ReturnDocument.AFTER
            )

            return {"message": "Claim updated successfully.", "status": 200}
        

        elif check == "confirmed" and result.get("status") != "approved" and result.get("status") != "exception":
            # Update extraction status in extraction_results collection
            await extraction_collection.update_one(
                {"_id": claim_id},
                {"$set": {"status": "approved"}}
            )

            await version_collection.insert_one({
                "file_id": file_id,
                "extraction_id": claim_id,
                "version": next_version,
                "claim": claim_json,
                "created_at": datetime.now(timezone.utc),
                "updated_by": updated_by,
                "status": "approved"
            })

            await version_collection.find_one_and_update(
                query,
                {"$set": {"status": "approved"}},
                sort=[("created_at", 1)],
                return_document=True
            )

            result = await version_collection.find_one(query, sort=[("created_at", 1)])
            predefined_json = result.get("claim", {})
            # ---------- apply user updates ----------
            updated_claim = apply_user_updates(predefined_json, claim_json)

            # ---------- version calculation ----------
            await version_collection.find_one_and_update(
                {"extraction_id": claim_id},
                {
                    "$set": {
                        "claim": updated_claim,
                        "updated_at": datetime.now(timezone.utc)
                    }
                },
                sort=[("created_at", 1)],   # first record (earliest)
                return_document=ReturnDocument.AFTER
            )
            return {"message": "Claim approved successfully.", "status": 200}
        
        
    except Exception as e:
        logger.error(f"Error saving claims data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save claims data.")

    
