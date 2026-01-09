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
    # claim_id: str

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

        #=============User role================
        cur_role = pg.cursor()
        cur_role.execute(
        """
        SELECT role
        FROM organization_memberships
        WHERE user_id = %s
        """,
        (user_id,)
        )
        user_role = cur_role.fetchone()
        print("User role===========:", user_role   )
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

        # ---------------------------
        # STATUS OPTIONS
        # ---------------------------
        status_list = [
            {"label": "All Statuses", "value": "all"},
            {"label": "Pending Review", "value": "pending_review"},
            {"label": "AI Processing", "value": "ai_processing"},
            {"label": "Approved", "value": "approved"},
            {"label": "In Review", "value": "in_review"},
        ]

        # ---------------------------
        # CONFIDENCE OPTIONS
        # ---------------------------
        confidence_list = [
            {"label": "All Confidence", "value": "all"},
            {"label": "High (90%+)", "value": "high"},
            {"label": "Medium (80-89%)", "value": "medium"},
            {"label": "Low (<80%)", "value": "low"},
        ]

        table_headers = [
            {"field": "fileName", "label": "File", "isSortable": True},
            {"field": "payer", "label": "Payer", "isSortable": True},
            {"field": "status", "label": "Status", "isSortable": True},
            {
                "field": "reviewer",
                "label": "Reviewer",
                "editable": {
                    "type": "dropdown",
                    "placeholder": "Select Reviewer",
                    "options": reviewer_options,
                },
            },
            {"field": "uploaded", "label": "Uploaded", "isDate": True, "isSortable": True},
            {
                "label": "Actions",
                "actions": [
                    {
                        "type": "generate 835",
                        "icon": "pi pi-file-check",
                        "roleAccess": ["admin"],
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
        role = user_role[0].lower()
        if role == "reviewer":
            mongo_query = {
                "fileId": {"$in": mongo_file_ids},
                "status": {
                    "$nin": ["need_template", "assign_payer", "ocr_failed"]
                },
                "reviewerId": {"$in": [user_id]}
            }
        else:
            print("User role is not reviewer")  
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
            claims_table_headers = [
                # {"field": "fileName", "label": "File"},
               
                {"field": "claim_number", "label": "Claim Number"},
                {"field": "payer", "label": "Payer"},
                {"field": "status", "label": "Status"},
                {"field": "uploaded", "label": "Uploaded", "isDate": True},
                {
                    "label": "Actions",
                    "actions": [
                        {"type": "view", "icon": "pi pi-eye", "roleAccess": ["admin", "reviewer", "viewer"]},
                        {"type": "approve", "icon": "pi pi-check-circle", "roleAccess": ["admin", "reviewer"]},
                        {"type": "reject", "icon": "pi pi-times-circle", "roleAccess": ["admin", "reviewer"]},
                    ],
                },
            ]
            claims_table_data = []
            for ext in extractions:
                ext_status = ext.get("status", "")
                ext_payer = ext.get("payerName", "")
                ext_filename = filename or ""
                claim_number = ext.get("claimNumber", "N/A")
                conf_val = float(ext.get("aiConfidence") or 0)
                claim_line_id = ext.get("_id", "")
                claims_table_data.append({
                    "file_id": file_id,
                    "claim_id": claim_line_id,
                    # "fileName": ext_filename,
                    "claim_number": claim_number,
                    "payer": ext_payer or payer_name or "-",
                    "status": ext_status,
                    "uploaded": uploaded_at,
                    "confidence": conf_val,
                    "isReviewed": ext_status in ["approved", "rejected", "exception"],

                })
            # If no extractions, add a default row for ai_processing
            if file_status == "ai_processing" and not extractions:
                claims_table_data.append({
                    "file_id": file_id,
                    "fileName": filename,
                    "payer": payer_name or "-",
                    "status": file_status,
                    "uploaded": uploaded_at,
                })
            table_rows.append({
                "file_id": file_id,
                "fileName": filename,
                "payer": payer_name or "-",
                "status": file_status,
                "reviewer": reviewer_id or "Unassigned",
                "uploaded": uploaded_at,
                "claims_data": {
                    "tableHeaders": claims_table_headers,
                    "tableData": claims_table_data,
                } if claims_table_data else None,
                "is_processing": True if file_status == 'ai_processing' else False,
            })
        
        # ---------------------------
        # APPLY FILTERS
        # ---------------------------
        filtered_rows = []
        for row in table_rows:
            # Search filter - search in fileName, payer, and claims data
            if search:
                search_lower = search.lower()
                search_str = f"{row['fileName']} {row['payer']}".lower()
                
                # Also search in claims data if available
                if row.get('claims_data') and row['claims_data'].get('tableData'):
                    for claim in row['claims_data']['tableData']:
                        search_str += f" {claim.get('fileName', '')} {claim.get('payer', '')} {claim.get('status', '')}".lower()
                
                if search_lower not in search_str:
                    continue
            
            # Payer filter
            if payer != "all":
                if payer.lower() not in row['payer'].lower():
                    continue
            
            # Status filter
            if status != "all":
                if row['status'] != status:
                    continue
            
            # Confidence filter - check claims data for confidence values
            if confidence_cat != "all":
                has_matching_confidence = False
                if row.get('claims_data') and row['claims_data'].get('tableData'):
                    for claim in row['claims_data']['tableData']:
                        conf_val = claim.get('confidence', 0)
                        if confidence_cat == "high" and conf_val >= 90:
                            has_matching_confidence = True
                            break
                        elif confidence_cat == "medium" and 80 <= conf_val < 90:
                            has_matching_confidence = True
                            break
                        elif confidence_cat == "low" and conf_val < 80:
                            has_matching_confidence = True
                            break
                if not has_matching_confidence:
                    continue
            
            filtered_rows.append(row)
        
        # ---------------------------
        # PAGINATION
        # ---------------------------
        total_records = len(filtered_rows)

        total_pages = (total_records + page_size - 1) // page_size
        if page > total_pages and total_pages > 0:
            page = total_pages

        start = (page - 1) * page_size
        end = start + page_size
        paginated_rows = filtered_rows[start:end]

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
            "payer_list": payer_list,
            "status_list": status_list,
            "confidence_list": confidence_list,
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
        cur.execute(
            """
            UPDATE upload_files
            SET reviwer_id = %s
            WHERE id = %s
            """,
            (payload.reviewer_id, payload.file_id)
        )
        conn.commit()

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

