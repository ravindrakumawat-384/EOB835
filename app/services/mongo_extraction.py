from pymongo import MongoClient
from typing import Dict, Any
import uuid
import datetime
import json
from ..utils.logger import get_logger
import app.common.db.db as db_module

logger = get_logger(__name__)

def store_extraction_result(file_id: str, ai_result: Dict[str, Any], raw_text: str) -> str:
   
    # Use your actual DB name 
    ext_collection = db_module.db["extraction_results"]  
    
    # Import here to avoid circular imports
    from .ai_claim_extractor import flatten_claims
    
    # Get flattened claims for easier querying
    flat_claims = flatten_claims(ai_result) if ai_result else []
    
    # Print AI extraction result for debugging
    for i, claim in enumerate(flat_claims, 1):
        print(f"\n--- CLAIM {i} ---")
        
    
    # Save each claim as a separate document with its own _id
    inserted_ids = []
    if flat_claims:
        for claim in flat_claims:
            claim_doc = {
                "_id": str(uuid.uuid4()),
                "fileId": file_id,
                "rawExtracted": raw_text,
                "claim": claim,
                "aiConfidence": ai_result.get('confidence', 0) if isinstance(ai_result, dict) else 0,
                "extractionStatus": "success",
                "payerName": claim.get('payer_name', 'Unknown'),
                "claimNumber": claim.get('claim_number', 'N/A'),
                "totalExtractedAmount": claim.get('total_paid_amount', 0),
                "createdAt": datetime.datetime.utcnow()
            }
            ext_collection.insert_one(claim_doc)
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
