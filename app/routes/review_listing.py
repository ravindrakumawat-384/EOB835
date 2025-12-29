from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import app.common.db.db as db_module
from ..utils.logger import get_logger
from bson import ObjectId
import os
import re
import datetime
from app.common.db.review_listing_schema import *
# from ..services.pg_upload_files import get_pg_conn
from app.common.db.pg_db import get_pg_conn
from pydantic import BaseModel
from app.common.db.db import init_db
from ..services.auth_deps import get_current_user, require_role

DB = init_db()
logger = get_logger(__name__)


class UpdateReviewerRequest(BaseModel):
    file_id: str
    reviewer_id: str
    claim_id: str

class UpdateReviewerResponse(BaseModel):
    status: int
    message: str
    file_id: str
    reviewer_id: str


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
    if "complete" in r or r == "approved":
        return "Approved"
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

@router.get("/summary", response_model=None, response_model_exclude_none=True)
async def review_queue(
    user: Dict[str, Any] = Depends(get_current_user),
    org_id: str = Query(...),
    search: Optional[str] = Query(None),
    payer: Optional[str] = Query("all"),
    status: Optional[str] = Query("all"),
    confidence_cat: Optional[str] = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=1000),
):
    try:
        pg = get_pg_conn()

        user_id = user.get("id")
        
        if status == "pending":
            status = "pending_review"
        elif status == "ai_process":
            status = "ai_processing"
        else:
            status = status
            
        #=============Payer name================
        cur_opts1 = pg.cursor()
        cur_opts1.execute(
        """
        SELECT id::text, name
        FROM payers
        WHERE org_id = %s
        ORDER BY name
        """,
        (org_id,)
        )
        payers = cur_opts1.fetchall()

        # optional: convert to list of dicts
        payer_list = [{"label": "All Payers", "value": "all"}] + [
        {"label": row[1], "value": row[1]} for row in payers
    ]

        # ---------------------------
        # REVIEWER OPTIONS
        # ---------------------------
        cur_opts2 = pg.cursor()
        cur_opts2.execute(
            """
            SELECT DISTINCT u.id::text, u.full_name
            FROM organization_memberships m
            JOIN users u ON u.id = m.user_id
            WHERE m.org_id = %s
            ORDER BY u.full_name
            """,
            (org_id,),
        )
        reviewer_rows = cur_opts2.fetchall()
        cur_opts2.close()

        reviewer_options = [{"label": "Unassigned", "value": "unassigned"}] + [
            {"label": r[1], "value": r[0]} for r in reviewer_rows if r[1]
        ]

        table_headers = [
            {"field": "fileName", "label": "File"},
            {"field": "payer", "label": "Payer"},
            {"field": "claim_number", "label": "Claim Number"}, 
            {"field": "confidence", "label": "Confidence"},
            {"field": "status", "label": "Status"},
            {
                "field": "reviewer",
                "label": "Reviewer",
                "editable": {
                    "type": "dropdown",
                    "placeholder": "Select Reviewer",
                    "options": reviewer_options,
                },
            },
            {"field": "uploaded", "label": "Uploaded", "isDate": True},
            {
                "label": "Actions",
                "actions": [
                    {
                        "type": "view",
                        "icon": "pi pi-eye",
                        "styleClass": "p-button-text p-button-sm",
                    }
                ],
            },
        ]

        # ---------------------------
        # POSTGRES (NO PAGINATION HERE)
        # ---------------------------
        where = ["uf.org_id = %s"]
        params = [org_id]

        # Remove status filter from SQL; will filter on extraction_results below

        # Remove payer filter from SQL; will filter on extraction_results below

        # NOTE: Search filter is NOT applied here in PostgreSQL because 
        # claim_number is stored in MongoDB (extraction_results).
        # Search filtering happens later at the MongoDB extraction level.

        where_sql = " AND ".join(where)

        cur = pg.cursor()
        cur.execute(
            f"""
            SELECT
                uf.id::text,
                uf.original_filename,
                p.name,
                uf.processing_status,
                uf.reviwer_id,
                uf.uploaded_at
            FROM upload_files uf
            LEFT JOIN payers p ON p.id = uf.detected_payer_id
            LEFT JOIN users u ON u.id = uf.uploaded_by
            WHERE {where_sql}
            ORDER BY uf.uploaded_at DESC
            """,
            params,
        )
        pg_rows = cur.fetchall()
        cur.close()

        if not pg_rows:
            return {
                "success": True,
                "tableData": {
                    "tableHeaders": table_headers,
                    "tableData": [],
                    "pagination": {"total": 0, "page": page, "page_size": page_size},
                    "total_records": 0,
                },
            }

        # ---------------------------
        # MONGO EXTRACTIONS
        # ---------------------------
        mongo_file_ids = [r[0] for r in pg_rows]

        # Fetch all extraction results - search filtering happens at application level
        # because filename comes from PostgreSQL, not MongoDB
        mongo_query = {
            "fileId": {"$in": mongo_file_ids},
            "status": {
                "$nin": ["need_template", "assign_payer", "ocr_failed"]
            }
        }

        mongo_docs = await db_module.db["extraction_results"].find(mongo_query).to_list(length=None)

        extraction_map = {}
        for d in mongo_docs:
            fid = d["fileId"].replace("store", "")
            extraction_map.setdefault(fid, []).append(d)

        # ---------------------------
        # BUILD ALL ROWS FIRST
        # ---------------------------
        table_rows = []

        for r in pg_rows:
            file_id, filename, payer_name, file_status, reviewer_id, uploaded_at = r
            extractions = extraction_map.get(file_id, [])
            # Build a search string for filtering
            search_str = f"{filename} {payer_name or ''} {file_status} {reviewer_id or ''}".lower()
            # Handle ai_processing rows with all filters
            if file_status == "ai_processing" and not extractions:
                if status in ("all", "ai_processing"):
                    # Apply search filter
                    if search and search.lower() not in search_str:
                        continue
                    # Apply payer filter
                    if payer != "all" and (not payer_name or payer.lower() not in payer_name.lower()):
                        continue
                    # ai_processing confidence is always 0, so filter accordingly
                    if confidence_cat == "high":
                        continue
                    if confidence_cat == "medium":
                        continue
                    if confidence_cat == "low":
                        pass  # 0 is < 80, so it's low
                    table_rows.append(
                        {
                            "file_id": file_id,
                            "claim_id": None,
                            "fileName": filename,
                            "payer": payer_name or "-",
                            "claim_number": "-",
                            "confidence": "0",
                            "status": file_status,
                            "reviewer": reviewer_id or "Unassigned",
                            "uploaded": uploaded_at,
                            "is_processing": True,
                        }
                    )
            # Otherwise, use extraction logic as before, but filter by all filters
            for ext in extractions:
                ext_status = ext.get("status", "")
                ext_payer = ext.get("payerName", "")
                ext_filename = filename or ""
                ext_reviewer = reviewer_id or ""
                claim_number = ext.get("claimNumber", "N/A")
                ext_search_str = f"{ext_filename} {ext_payer} {ext_status} {ext_reviewer} {claim_number}".lower()
                if status != "all" and ext_status != status:
                    continue
                if payer != "all" and (not ext_payer or payer.lower() not in ext_payer.lower()):
                    continue
                conf_val = float(ext.get("aiConfidence") or 0)
                if confidence_cat != "all":
                    if confidence_cat == "high" and conf_val < 90:
                        continue
                    if confidence_cat == "medium" and not (80 <= conf_val < 90):
                        continue
                    if confidence_cat == "low" and conf_val >= 80:
                        continue
                # Apply search filter
                if search and search.lower() not in ext_search_str:
                    continue
                claim_line_id = ext.get("_id", "")
                reviewer_ids = ext.get("reviewerId", None)
                table_rows.append(
                    {
                        "file_id": file_id,
                        "claim_id": claim_line_id, 
                        "fileName": filename,
                        "payer": ext.get("payerName") or payer_name or "Unknown",
                        "claim_number": claim_number or "N/A",
                        "confidence": f"{int(conf_val)}",
                        "status": ext_status,
                        "reviewer": reviewer_ids or "Unassigned",
                        "uploaded": uploaded_at,
                    }
                )
        # ---------------------------
        # ✅ FIXED PAGINATION (ONLY CHANGE)
        # ---------------------------
        # Show only 'pending_review' count in total_records
        total_records = sum(1 for row in table_rows if row.get('status') == 'pending_review')

        total_pages = (total_records + page_size - 1) // page_size
        if page > total_pages and total_pages > 0:
            page = total_pages

        start = (page - 1) * page_size
        end = start + page_size
        paginated_rows = table_rows[start:end]

        return {
            "message": "Review queue data fetched successfully.",
            "tableData": {
                "tableHeaders": table_headers,
                "tableData": paginated_rows,
                "pagination": {
                    "total": total_records,
                    "page": page,
                    "page_size": page_size,
                },
                "total_records": total_records,
            },
            "payer_list": payer_list
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while fetching review queue data",
        )


@router.patch("/update_reviewer", response_model=UpdateReviewerResponse)
async def update_reviewer(payload: UpdateReviewerRequest):
    conn = get_pg_conn()
    cur = conn.cursor()
    try:
        collection = DB["extraction_results"]
        claim_version = DB["claim_version"] 
        
        collection.update_one(
            {
                "_id": payload.claim_id,
                "fileId": payload.file_id
            },
            {
                "$set": {
                    "reviewerId": payload.reviewer_id
                }
            }
        )

        claim_version.update_one(
            {
                "extraction_id": payload.claim_id,
                "file_id": payload.file_id
            },
            {
                "$set": {
                    "updated_by": payload.reviewer_id,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )   

        return UpdateReviewerResponse(
            status=200,
            message="Reviewer updated successfully",
            file_id=payload.file_id,
            reviewer_id=payload.reviewer_id,
        )
    except Exception as exc:
        conn.rollback()
        logger.exception("update_reviewer error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong while updating reviewer.")
    finally:
        cur.close()
        conn.close()
