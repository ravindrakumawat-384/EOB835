
from fastapi import APIRouter, Depends, HTTPException
from ..common.db.db import db
import app.common.db.db as db_module
from ..utils.logger import get_logger
logger = get_logger(__name__)

from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/orgs", tags=["organizations"])


def serialize_org(doc: dict) -> dict:
    """
    Convert MongoDB document into JSON-safe organization object.
    """
    if not doc:
        return None

    return {
        "id": doc.get("id"),
        "name": doc.get("name"),
        "slug": doc.get("slug"),
        "status": doc.get("status"),
        "settings_json": doc.get("settings_json", {}),
        "logo_file_path": doc.get("logo_file_path"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }



# @router.get("/")
# async def list_orgs():
#     docs = []
#     cursor = db_module.db.organizations.find({})
#     async for doc in cursor:
#         docs.append(doc)
#     logger.info(f"Fetched {len(docs)} organizations")
#     return {"count": len(docs), "items": docs}


@router.get("")
async def list_orgs():
    """
    Return all organizations in clean JSON format.
    """
    try:
        cursor = db_module.db.organizations.find({}, {"_id": 0})  # remove MongoDB ObjectId
        orgs = []
        async for doc in cursor:
            orgs.append(serialize_org(doc))
        logger.info(f"Fetched {len(orgs)} organizations")
        return {
            "success": True,
            "message": "Organizations fetched successfully",
            "count": len(orgs),
            "items": orgs,
        }
    except Exception as e:
        logger.error(f"Failed to fetch organizations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch organizations")