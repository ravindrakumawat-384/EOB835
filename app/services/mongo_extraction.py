from pymongo import MongoClient
from typing import Dict, Any
import uuid
import datetime
import json
from ..utils.logger import get_logger
import app.common.db.db as db_module

logger = get_logger(__name__)

# def store_extraction_result(file_id: str, ai_result: Dict[str, Any], raw_text: str, payer_name: str, uploaded_by: str) -> str:
def store_extraction_result(file_id: str, ai_result: Dict[str, Any], payer_name: str, uploaded_by: str) -> str:
   
    # Use your actual DB name 
    ext_collection = db_module.db["extraction_results"]  
    claim_version = db_module.db["claim_version"]  
    
    # Import here to avoid circular imports
    from .ai_claim_extractor import flatten_claims2
    
    # Get flattened claims for easier querying
    flat_claims = flatten_claims2(ai_result) if ai_result else []
    print('flat_claims======', flat_claims)
    # Print AI extraction result for debugging
    for i, claim in enumerate(flat_claims, 1):
        print(f"\n--- CLAIM {i} ---")
        
    
    # Save each claim as a separate document with the requested structure
    inserted_ids = []
    if flat_claims:
        # for claim in flat_claims:
        claim_doc = {
            "_id": str(uuid.uuid4()),
            "fileId": file_id,
            # "rawExtracted": raw_text,
            "rawExtracted": "raw_text",
            "claim": flat_claims["section"],
            "aiConfidence": 90,
            "extractionStatus": "success",
            "payerName": payer_name,
            "claimNumber": flat_claims["claim_number"],
            "totalExtractedAmount": flat_claims["total_paid"],
            "createdAt": datetime.datetime.utcnow(),
            "status": "pending_review",
            "reviewerId": uploaded_by
        }
        ext_collection.insert_one(claim_doc)

        claim_version.insert_one({
            "file_id": file_id,
            "extraction_id": claim_doc['_id'],
            "version": "1.0",
            "claim": flat_claims["section"],
            "created_at": datetime.datetime.utcnow(),
            "updated_by": uploaded_by,
            "status": "pending_review"})


        logger.info(f"Stored extraction result for file {file_id} in MongoDB with _id {claim_doc['_id']}")
        inserted_ids.append(claim_doc['_id'])
    else:
        # If no claims, store a failed extraction doc
        claim_doc = {
            "_id": str(uuid.uuid4()),
            "fileId": file_id,
            "rawExtracted": raw_text,
            "extractionStatus": "failed",
            "createdAt": datetime.datetime.utcnow()
        }
        ext_collection.insert_one(claim_doc)
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
