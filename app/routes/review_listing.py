from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import app.common.db.db as db_module
from ..utils.logger import get_logger
from bson import ObjectId
import os
import re
import datetime
from app.common.db.review_listing_schema import *

logger = get_logger(__name__)


# --- helpers ---
def regex_escape(q: str) -> str:
    return re.escape(q)

def compute_confidence_label(percent: Optional[float]) -> str:
    try:
        p = float(percent) if percent is not None else 0.0
    except Exception:
        p = 0.0
    if p >= 90:
        label = "High"
    elif p > 80:
        label = "Medium"
    else:
        label = "Low"
    pct = f"{int(round(p))}%"
    return f"{label} {pct}"

def normalize_status(raw: Optional[str]) -> str:
    if not raw:
        return "Pending Review"
    r = str(raw).strip().lower()
    if "complete" in r or r == "completed":
        return "Completed"
    if r in ("review", "in review", "under review"):
        return "Review"
    # default fallback
    return "Pending Review"

# --- DB client & collections ---

# Ensure db is initialized
if db_module.db is None:
    db_module.init_db()
files_col = db_module.db["upload_files"]         # file documents
claims_col = db_module.db["claims"]              # claims documents
payers_col = db_module.db["payers"]              # payer documents (field: name)
batches_col = db_module.db["upload_batches"]    # upload batches (field: created_at)

router = APIRouter(prefix="/review_queue", tags=["review"])

@router.get("/summary", response_model=ReviewResponse)

async def review_queue(
    org_id: str = Query(..., description="organization id (required)"),
    q: Optional[str] = Query(None, description="Search across filename, claim_id, patient_name, reviewer, payer, status, confidence"),
    payer: Optional[str] = Query(None, description="payer name or payer _id"),
    status: Optional[str] = Query(None),
    confidence_cat: Optional[str] = Query(None, alias="confidence"),
    page: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=200),
    sort_by: str = Query("resolved_uploaded_at"),
    sort_dir: str = Query("desc"),
):
    try:
        if not org_id:
            raise HTTPException(status_code=400, detail={"message": "missing_org_id"})

        # -------------------------------
        # 1. INITIAL MATCH
        # -------------------------------
        initial_match = {"org_id": org_id}

        if status:
            initial_match["$or"] = [
                {"processing_status": status},
                {"status": status},
            ]

        if confidence_cat:
            c = confidence_cat.lower()
            if c == "high":
                initial_match["ai_payer_confidence"] = {"$gte": 90}
            elif c == "medium":
                initial_match["ai_payer_confidence"] = {"$gte": 80, "$lt": 90}
            elif c == "low":
                initial_match["ai_payer_confidence"] = {"$lt": 80}

        pipeline = [
            {"$match": initial_match},

            # --------------------------------
            # 2. RESOLVE payer_oid FROM detected_payer_id
            # --------------------------------
            {
                "$addFields": {
                    "payer_oid": {
                        "$cond": [
                            {"$eq": [{"$type": "$detected_payer_id"}, "string"]},
                            {"$convert": {"input": "$detected_payer_id", "to": "objectId", "onError": None, "onNull": None}},
                            "$detected_payer_id",
                        ]
                    }
                }
            },

            # -------------------------------
            # 3. LOOKUP PAYER
            # -------------------------------
            {
                "$lookup": {
                    "from": "payers",
                    "localField": "payer_oid",
                    "foreignField": "_id",
                    "as": "_payer_doc",
                }
            },
            {
                "$addFields": {
                    "resolved_payer_name": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$_payer_doc.name", 0]},
                            None,
                        ]
                    }
                }
            },

            # -------------------------------
            # 4. LOOKUP UPLOAD BATCH
            # -------------------------------
            {
                "$lookup": {
                    "from": "upload_batches",
                    "localField": "batch_id",
                    "foreignField": "_id",
                    "as": "_batch_doc",
                }
            },
            {
                "$addFields": {
                    "resolved_uploaded_at": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$_batch_doc.created_at", 0]},
                            "$uploaded_at",
                        ]
                    }
                }
            },

            # -------------------------------
            # 5. LOOKUP CLAIMS (file_id stored as string)
            # -------------------------------
            {
                "$lookup": {
                    "from": "claims",
                    "let": {"file_id_str": {"$toString": "$_id"}},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$file_id", "$$file_id_str"]}}},
                        {"$project": {"claim_number": 1, "patient_name": 1}},
                    ],
                    "as": "_claims",
                }
            },

            {
                "$addFields": {
                    "claims_count": {"$size": {"$ifNull": ["$_claims", []]}},
                    "confidence_percent": {"$ifNull": ["$ai_payer_confidence", 0]},
                    "resolved_status": {"$ifNull": ["$status", "$processing_status", "Pending Review"]},
                }
            },

            # -------------------------------
            # 6. LOOKUP reviewer_session → users
            # -------------------------------
            {
                "$lookup": {
                    "from": "reviewer_session",
                    "let": {
                        "claim_ids": {
                            "$map": {"input": "$_claims", "as": "c", "in": {"$toString": "$$c._id"}}
                        }
                    },
                    "pipeline": [
                        {"$match": {"$expr": {"$in": ["$claim_id", "$$claim_ids"]}}},
                        {"$sort": {"started_at": -1}},
                        {"$limit": 1},
                    ],
                    "as": "_latest_review_session",
                }
            },
            {
                "$addFields": {
                    "latest_review_session": {"$arrayElemAt": ["$_latest_review_session", 0]}
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "latest_review_session.reviewer_id",
                    "foreignField": "_id",
                    "as": "_reviewer_user",
                }
            },
            {
                "$addFields": {
                    "reviewer_name": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$_reviewer_user.name", 0]},
                            "Unassigned",
                        ]
                    }
                }
            },

            # -------------------------------
            # 7. PROJECT OUT HEAVY FIELDS
            # -------------------------------
            {
                "$project": {
                    "_payer_doc": 0,
                    "_batch_doc": 0,
                    "_claims": 0,
                    "_latest_review_session": 0,
                    "_reviewer_user": 0,
                }
            },
        ]

        # -------------------------------
        # 8. SEARCH & FILTER POST MATCH
        # -------------------------------
        post_match = []

        if payer:
            try:
                oid = ObjectId(payer)
                post_match.append({"payer_oid": oid})
            except:
                post_match.append({"resolved_payer_name": {"$regex": f"^{re.escape(payer)}$", "$options": "i"}})

        if q:
            esc = re.escape(q)
            search_or = [
                {"original_filename": {"$regex": esc, "$options": "i"}},
                {"resolved_payer_name": {"$regex": esc, "$options": "i"}},
                {"reviewer_name": {"$regex": esc, "$options": "i"}},
                {"resolved_status": {"$regex": esc, "$options": "i"}},
            ]
            post_match.append({"$or": search_or})

        if post_match:
            pipeline.append({"$match": {"$and": post_match}})

        # -------------------------------
        # 9. SORT AND PAGINATE
        # -------------------------------
        sort_direction = -1 if sort_dir.lower() == "desc" else 1
        pipeline.append({"$sort": {sort_by: sort_direction}})

        count_pipeline = pipeline + [{"$count": "total"}]

        skip = (page - 1) * page_size
        pipeline.extend([{"$skip": skip}, {"$limit": page_size}])

        total_res = await files_col.aggregate(count_pipeline).to_list(length=1)
        total = total_res[0]["total"] if total_res else 0
        docs = await files_col.aggregate(pipeline).to_list(length=page_size)

        # -------------------------------
        # 10. BUILD RESPONSE ROWS
        # -------------------------------
        rows = []
        for d in docs:
            filename = d.get("original_filename", "")

            payer_name = d.get("resolved_payer_name") or "Unknown"

            conf_percent = d.get("confidence_percent", 0)
            conf_label = "High" if conf_percent >= 90 else "Medium" if conf_percent >= 80 else "Low"
            confidence_str = f"{conf_label} {int(conf_percent)}%"

            reviewer = d.get("reviewer_name", "Unassigned")
            status_val = d.get("resolved_status")
            claims_count = d.get("claims_count", 0)

            uploaded_at = d.get("resolved_uploaded_at")
            uploaded_str = uploaded_at.strftime("%Y-%m-%d") if isinstance(uploaded_at, datetime.datetime) else str(uploaded_at)[:10]

            rows.append({
                "fileName": filename,
                "payer": payer_name,
                "confidence": confidence_str,
                "status": status_val,
                "reviewer": reviewer,
                "uploaded": uploaded_str,
                "claims": claims_count
            })

        # -------------------------------
        # 11. FINAL RESPONSE
        # -------------------------------
        headers = [
            {"field": "fileName", "label": "File Name"},
            {"field": "payer", "label": "Payer"},
            {"field": "confidence", "label": "Confidence"},
            {"field": "status", "label": "Status"},
            {"field": "reviewer", "label": "Reviewer"},
            {"field": "uploaded", "label": "Uploaded"},
            {"field": "claims", "label": "Claims"},
            {"label": "Actions",
                        "actions": [{"type": "view", "icon": "pi pi-eye", "styleClass": "p-button-text p-button-sm"}]
                    }
        ]

        return {
            "tableHeaders": headers,
            "tableData": rows,
            "pagination": {"total": total, "page": page, "page_size": page_size},
            "totalRecords": total,
        }

    except Exception as exc:
        logger.exception("review_queue error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong while fetching review queue listing data.")
