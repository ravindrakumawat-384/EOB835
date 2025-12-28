from pymongo import MongoClient
from typing import Dict, Any
import uuid
import datetime
import json
from ..utils.logger import get_logger
import app.common.db.db as db_module

logger = get_logger(__name__)

# def store_extraction_result(file_id: str, ai_result: Dict[str, Any], raw_text: str, payer_name: str, uploaded_by: str) -> str:
async def store_extraction_result(db, file_id: str, ai_result: Dict[str, Any], payer_name: str, uploaded_by: str) -> str:
    print('ai_result======', ai_result)
    # Use the passed db instance
    ext_collection = db["extraction_results"]  
    claim_version = db["claim_version"]  
    
    # Import here to avoid circular imports
    from .ai_claim_extractor import flatten_claims2
    
    # Get flattened claims for easier querying
    flat_claims = flatten_claims2(ai_result) if ai_result else []
    print('flat_claims======', flat_claims)
    
    # Save each claim as a separate document with the requested structure
    inserted_ids = []
    if flat_claims:
        # User's code had a single claim_doc logic, but flat_claims might be a list or dict depending on flatten_claims2
        # Based on user's previous code, they treat flat_claims as a dict with "section", "claim_number", etc.
        # However, flatten_claims2 usually returns a list or a dict. 
        # Let's assume it's a dict for now as per user's logic, but handle it safely.
        
        claim_doc = {
            "_id": str(uuid.uuid4()),
            "fileId": file_id,
            "rawExtracted": "raw_text",
            "claim": flat_claims.get("section") if isinstance(flat_claims, dict) else "",
            "aiConfidence": flat_claims.get("aiConfidence", 0) if isinstance(flat_claims, dict) else 0,
            "extractionStatus": "success",
            "payerName": payer_name,
            "claimNumber": flat_claims.get("claim_number") if isinstance(flat_claims, dict) else 0,
            "totalExtractedAmount": flat_claims.get("total_paid") if isinstance(flat_claims, dict) else 0,
            "createdAt": datetime.datetime.now(datetime.timezone.utc),
            "status": "pending_review",
            "reviewerId": uploaded_by
        }
        await ext_collection.insert_one(claim_doc)

        await claim_version.insert_one({
            "file_id": file_id,
            "extraction_id": claim_doc['_id'],
            "version": "1.0",
            "claim": flat_claims.get("section") if isinstance(flat_claims, dict) else "",
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "updated_by": uploaded_by,
            "status": "pending_review"})

        logger.info(f"Stored extraction result for file {file_id} in MongoDB with _id {claim_doc['_id']}")
        inserted_ids.append(claim_doc['_id'])
    else:
        # If no claims, store a failed extraction doc
        claim_doc = {
            "_id": str(uuid.uuid4()),
            "fileId": file_id,
            "rawExtracted": "raw_text",
            "extractionStatus": "failed",
            "createdAt": datetime.datetime.now(datetime.timezone.utc)
        }
        await ext_collection.insert_one(claim_doc)
        logger.info(f"Stored failed extraction result for file {file_id} in MongoDB with _id {claim_doc['_id']}")
        inserted_ids.append(claim_doc['_id'])
    return inserted_ids

# Dummy AI extraction function (replace with real model)
def extract_json_ai(file_content: bytes) -> Dict[str, Any]:
    # For demo, return a fake claim structure
    return {
        "claims": [
            {
                "payer_name": "Demo Payer",
                "patient_name": "John Doe",
                "claim_number": "123456",
                "amount": 100.0
            }
        ]
    }
