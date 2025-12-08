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
    print('='*80)
    print('🤖 AI EXTRACTION RESULT:')
    print(json.dumps(ai_result, indent=2, default=str))
    print('='*80)
    print(f'📋 FLATTENED CLAIMS ({len(flat_claims)} separate claims):')
    for i, claim in enumerate(flat_claims, 1):
        print(f"\n--- CLAIM {i} ---")
        print(f"Claim Number: {claim.get('claim_number', 'N/A')}")
        print(f"Patient: {claim.get('patient_name', 'N/A')}")
        print(f"Payer: {claim.get('payer_name', 'N/A')}")
        print(f"Amount Paid: ${claim.get('total_paid_amount', 0)}")
        print(f"Member ID: {claim.get('member_id', 'N/A')}")
        print(f"Service Date: {claim.get('service_date_from', 'N/A')}")
    print('='*80)
    print('📄 RAW TEXT (first 500 chars):', raw_text[:500])
    print('='*80)
    
    doc = {
        "_id": str(uuid.uuid4()),
        "fileId": file_id,
        "rawExtracted": raw_text,
        "originalAiResult": ai_result,  # Store complete AI result
        "normalizedClaims": flat_claims,  # Store flattened claims - EACH claim is separate
        "separateClaimsCount": len(flat_claims),  # Number of individual claims
        "aiConfidence": ai_result.get('confidence', 0) if isinstance(ai_result, dict) else 0,
        "extractionStatus": "success" if (ai_result and ai_result.get('claims')) else "failed",
        "payerNames": list(set(claim.get('payer_name', 'Unknown') for claim in flat_claims)),
        "claimNumbers": [claim.get('claim_number', 'N/A') for claim in flat_claims],
        "totalExtractedAmount": sum(claim.get('total_paid_amount', 0) for claim in flat_claims),
        "processingNote": f"Extracted {len(flat_claims)} separate claims from document",
        "createdAt": datetime.datetime.utcnow()
    }
    result = ext_collection.insert_one(doc)
    logger.info(f"Stored extraction result for file {file_id} in MongoDB with _id {doc['_id']}")
    
    # Print what was stored
    print('💾 STORED IN MONGODB:')
    stored_summary = {k: v for k, v in doc.items() if k not in ['rawExtracted', 'originalAiResult']}
    print(json.dumps(stored_summary, indent=2, default=str))
    print('='*80)
    print(f"✅ SUMMARY: Stored {len(flat_claims)} SEPARATE claims in MongoDB collection 'extraction_results'")
    print('='*80)
    
    return doc["_id"]

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
