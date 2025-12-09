from fastapi import APIRouter
from typing import Dict, Any, List
import app.common.db.db as db_module
import json

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/latest-extraction")
def get_latest_extraction() -> Dict[str, Any]:
    """
    Get the latest extraction result from MongoDB for debugging.
    """
    ext_collection = db_module.db["extraction_results"]
    
    # Get the latest document
    latest_doc = ext_collection.find_one(sort=[("createdAt", -1)])
    
    if not latest_doc:
        return {"error": "No extraction results found"}
    
    # Convert ObjectId to string for JSON serialization
    if "_id" in latest_doc:
        latest_doc["_id"] = str(latest_doc["_id"])
    
    # Format for better readability
    response = {
        "summary": {
            "fileId": latest_doc.get("fileId"),
            "separateClaimsCount": latest_doc.get("separateClaimsCount", 0),
            "totalExtractedAmount": latest_doc.get("totalExtractedAmount", 0),
            "payerNames": latest_doc.get("payerNames", []),
            "claimNumbers": latest_doc.get("claimNumbers", []),
            "aiConfidence": latest_doc.get("aiConfidence", 0),
            "extractionStatus": latest_doc.get("extractionStatus")
        },
        "originalAiResult": latest_doc.get("originalAiResult", {}),
        "separateClaims": latest_doc.get("normalizedClaims", []),
        "rawTextPreview": latest_doc.get("rawExtracted", "")[:500] + "..." if latest_doc.get("rawExtracted") else ""
    }
    
    return response