from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from ..services.auth_deps import get_current_user, require_role
import app.common.db.db as db_module
from ..utils.logger import get_logger
from datetime import datetime, timezone
from ..common.db.dashboard_schemas import DashboardResponse

#log maintainer
logger = get_logger(__name__)


# Router
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/summary", response_model=DashboardResponse)

async def dashboard_summary() -> JSONResponse:
    """
    Dashboard summary (org-scoped) using upload_batches, upload_files, payers.
    """
    try:
        # org scoping: expect org identifier on authenticated user
        # org_id = user.get("org_id") 
        org_id = "653e1b000000000000000001"
        if not org_id:
            raise HTTPException(status_code=400, detail="org_id required in user context")

        BATCHES = "upload_batches"
        FILES = "upload_files"
        PAYERS = "payers"

        # correct collection access
        batches_col = db_module.db[BATCHES]
        files_col = db_module.db[FILES]
        payers_col = db_module.db[PAYERS]

        # ---------- WIDGET COUNTS (org-scoped) ----------
        base_match = {"org_id": org_id}
        uploaded = await batches_col.count_documents(base_match)
        processed = await batches_col.count_documents({**base_match, "status": "completed"})
        pending_review = await batches_col.count_documents({**base_match, "status": "processing"})
        exceptions = await batches_col.count_documents({**base_match, "status": "with_errors"})

        needs_template = await batches_col.count_documents({**base_match, "status": "needs_template"})
        if needs_template == 0:
            nt_pipeline = [
                {"$match": {"$and": [{"processing_status": "needs_template"}, {"org_id": org_id}]}},
                {"$group": {"_id": "$batch_id"}},
                {"$count": "total"}
            ]
            nt = await files_col.aggregate(nt_pipeline).to_list(length=1)
            needs_template = nt[0]["total"] if nt else 0

        # accuracy_percent = round((processed / uploaded * 100), 1) if uploaded else 0.0
        # ---------- ACCURACY PERCENT: ORG-LEVEL FROM upload_files.ai_payer_confidence ----------
        accuracy_pipeline = [
            {
                "$match": {
                    "org_id": org_id,
                    "ai_payer_confidence": {"$ne": None}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_conf": {"$avg": "$ai_payer_confidence"}
                }
            }
        ]

        acc = await files_col.aggregate(accuracy_pipeline).to_list(length=1)
        accuracy_percent = round(acc[0]["avg_conf"], 1) if acc else 0.0

        # ---------- AGGREGATION (org-scoped) ----------
        # convert batch._id -> string to match files.batch_id (string),
        # unwind files, convert files.detected_payer_id (string) -> ObjectId for lookup
        pipeline = [
            {"$match": {"org_id": org_id}},
            {"$sort": {"created_at": -1}},
            {"$addFields": {"batch_id_str": {"$toString": "$_id"}}},
            {
                "$lookup": {
                    "from": FILES,
                    "localField": "batch_id_str",
                    "foreignField": "batch_id",
                    "as": "files"
                }
            },
            {"$unwind": {"path": "$files", "preserveNullAndEmptyArrays": False}},
            # ensure file belongs to same org (defensive)
            {"$match": {"$expr": {"$eq": ["$files.org_id", org_id]}}},
            # convert payer id string -> ObjectId if present
            {
                "$addFields": {
                    "detected_payer_obj": {
                        "$cond": [
                            {"$and": [
                                {"$ne": ["$files.detected_payer_id", None]},
                                {"$ne": ["$files.detected_payer_id", ""]}
                            ]},
                            {"$toObjectId": "$files.detected_payer_id"},
                            None
                        ]
                    }
                }
            },
            {
                "$lookup": {
                    "from": PAYERS,
                    "localField": "detected_payer_obj",
                    "foreignField": "_id",
                    "as": "payer_doc"
                }
            },
            {"$unwind": {"path": "$payer_doc", "preserveNullAndEmptyArrays": True}},
            # ensure payer is org-scoped or global (payer.org_id may be null for global)
            {
                "$addFields": {
                    "payer_name": {
                        "$cond": [
                            {"$and": [
                                {"$ne": ["$payer_doc", None]},
                                {"$or": [
                                    {"$eq": ["$payer_doc.org_id", org_id]},
                                    {"$eq": ["$payer_doc.org_id", None]}
                                ]}
                            ]},
                            "$payer_doc.name",
                            None
                        ]
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "fileName": "$files.original_filename",
                    "payer": {"$ifNull": ["$payer_name", None]},
                    "status": "$status",
                    "created_at": "$created_at"
                }
            },
            {"$limit": 8}
        ]

        results = await batches_col.aggregate(pipeline).to_list(length=8)

        # ---------- HUMANIZE helper ----------
        def humanize(dt):
            if not dt:
                return "N/A"
            if isinstance(dt, str):
                try:
                    dt = dt.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt)
                except Exception:
                    return "N/A"
            if not isinstance(dt, datetime):
                try:
                    dt = dt.generation_time
                except Exception:
                    return "N/A"
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            diff = datetime.now(timezone.utc) - dt
            days = diff.days
            secs = diff.seconds
            if days > 0:
                return f"{days} day{'s' if days > 1 else ''} ago"
            hrs = secs // 3600
            if hrs > 0:
                return f"{hrs} hour{'s' if hrs > 1 else ''} ago"
            mins = (secs % 3600) // 60
            if mins > 0:
                return f"{mins} minute{'s' if mins > 1 else ''} ago"
            return "just now"

        # ---------- BUILD TABLE ROWS (ONLY REAL DATA, MAX 8) ----------
        table_rows = []
        for doc in results:
            fn = doc.get("fileName")
            if not fn:
                continue
            table_rows.append({
                "fileName": fn,
                "payer": doc.get("payer") or "Unknown Payer",
                "status": doc.get("status") or "Unknown",
                "uploaded": humanize(doc.get("created_at"))
            })
            if len(table_rows) >= 8:
                break

        resp_data = {
            "success": "Data retrieved successfully",
            "widgets": {
                "uploaded": uploaded,
                "processed": processed,
                "pendingReview": pending_review,
                "accuracyPercent": accuracy_percent,
                "exceptions": exceptions,
                "needsTemplate": needs_template
            },
            "recentUploadsData": {
                "total_records": len(table_rows),
                "tableHeaders": [
                    {"field": "fileName", "label": "File Name"},
                    {"field": "payer", "label": "Payer"},
                    {"field": "status", "label": "Status"},
                    {"field": "uploaded", "label": "Uploaded"},
                    {
                        "label": "Actions",
                        "actions": [{"type": "view", "icon": "pi pi-eye", "styleClass": "p-button-text p-button-sm"}]
                    }
                ],
                "tableData": table_rows
            },
            
            
        }

        return JSONResponse(content=resp_data, status_code=200)

    except Exception as e:
        logger.error("dashboard summary failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong while fetching dashboard data.")

