from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import app.common.db.db as db_module
from ..utils.logger import get_logger
from bson import ObjectId
import os
import re
import datetime
from app.common.db.review_listing_schema import *
from ..services.pg_upload_files import get_pg_conn

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

@router.get("/summary", response_model=ReviewResponse, response_model_exclude_none=True)
async def review_queue(
    org_id: str = Query(..., description="organization id (required)"),
    q: Optional[str] = Query(None, description="Search across filename, claim_id, patient_name, reviewer, payer, status, confidence"),
    payer: Optional[str] = Query(None, description="payer name or payer _id (comma-separated allowed)"),
    status: Optional[str] = Query(None, description="processing status to filter"),
    confidence_cat: Optional[str] = Query(None, alias="confidence", description="High/Medium/Low"),
    page: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=200),
    sort_by: str = Query("resolved_uploaded_at"),
    sort_dir: str = Query("desc"),
):
    try:
        if not org_id:
            raise HTTPException(status_code=400, detail={"message": "missing_org_id"})

        sort_map = {
            "fileName": "uf.original_filename",
            "original_filename": "uf.original_filename",
            "payer": "p.name",
            "confidence": "uf.ai_payer_confidence",
            "status": "uf.processing_status",
            "reviewer": "u.full_name",
            "uploaded": "uf.uploaded_at",
            "resolved_uploaded_at": "uf.uploaded_at",
        }
        mapped_sort = sort_map.get(sort_by, "uf.uploaded_at")
        sort_dir_val = "DESC" if str(sort_dir).lower() == "desc" else "ASC"

        pg = get_pg_conn()

        # payer options
        cur_opts = pg.cursor()
        try:
            cur_opts.execute("SELECT id::text, name FROM payers WHERE org_id = %s ORDER BY name", (org_id,))
            payer_rows = cur_opts.fetchall()
            payer_options = [{"label": r[1], "value": r[0]} for r in payer_rows]
        finally:
            cur_opts.close()

        # reviewer options (organization_memberships -> users)
        cur_opts2 = pg.cursor()
        try:
            cur_opts2.execute("""
                SELECT DISTINCT u.id::text, u.full_name
                FROM organization_memberships m
                JOIN users u ON u.id = m.user_id
                WHERE m.org_id = %s AND m.role = 'reviewer'
                ORDER BY u.full_name
            """, (org_id,))
            reviewer_rows = cur_opts2.fetchall()
            reviewer_options = [{"label": "Unassigned", "value": "Unassigned"}] + [
                {"label": rr[1], "value": rr[1]} for rr in reviewer_rows if rr[1]
            ]
        finally:
            cur_opts2.close()

        # canonical headers (include editable for reviewer as requested)
        final_headers = [
            {"field": "fileName", "label": "File"},
            {"field": "payer", "label": "Payer"},
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
            {"field": "uploaded", "label": "Uploaded"},
            {"label": "Actions", "actions": [{"type": "view", "icon": "pi pi-eye", "styleClass": "p-button-text p-button-sm"}]},
        ]

        # confidence filter from Mongo (get matching fileIds)
        mongo_file_ids: Optional[List[str]] = None
        if confidence_cat:
            c = confidence_cat.strip().lower()
            if c == "high":
                match_expr = {"$gte": 90}
            elif c == "medium":
                match_expr = {"$gte": 80, "$lt": 90}
            elif c == "low":
                match_expr = {"$lt": 80}
            else:
                match_expr = None

            if match_expr is not None:
                mongo_pipeline = [
                    {"$match": {"fileId": {"$exists": True}}},
                    {"$sort": {"createdAt": -1}},
                    {"$group": {"_id": "$fileId", "aiConfidence": {"$first": "$aiConfidence"}, "overallConfidence": {"$first": "$overallConfidence"}}},
                    {"$addFields": {"confidence": {"$convert": {"input": {"$ifNull": ["$aiConfidence", "$overallConfidence", 0]}, "to": "double", "onError": 0, "onNull": 0}}}},
                    {"$match": {"confidence": match_expr}},
                    {"$project": {"_id": 1}}
                ]
                mongo_docs = await db_module.db["extraction_results"].aggregate(mongo_pipeline).to_list(length=None)
                mongo_file_ids = [str(d["_id"]) for d in mongo_docs]

                if not mongo_file_ids:
                    return {
                        "tableHeaders": final_headers,
                        "tableData": [],
                        "pagination": {"total": 0, "page": page, "page_size": page_size},
                        "totalRecords": 0,
                    }

        # Build SQL WHERE
        where_clauses = ["uf.org_id = %s"]
        params: List[Any] = [org_id]

        if status:
            where_clauses.append("(uf.processing_status = %s OR uf.status = %s)")
            params.extend([status, status])

        if payer:
            # allow comma-separated payer id or name
            payer_terms = [p.strip() for p in payer.split(",") if p.strip()]
            payer_sub = []
            for term in payer_terms:
                payer_sub.append("p.id::text = %s")
                params.append(term)
                payer_sub.append("p.name ILIKE %s")
                params.append(f"%{term}%")
            where_clauses.append("(" + " OR ".join(payer_sub) + ")")

        if mongo_file_ids is not None:
            placeholders = ",".join(["%s"] * len(mongo_file_ids))
            where_clauses.append(f"uf.id::text IN ({placeholders})")
            params.extend(mongo_file_ids)

        if q:
            q_like = f"%{q}%"
            where_clauses.append("(uf.original_filename ILIKE %s OR p.name ILIKE %s OR u.full_name ILIKE %s OR uf.processing_status ILIKE %s OR EXISTS (SELECT 1 FROM claims c WHERE c.file_id::text = uf.id::text AND (c.claim_number ILIKE %s OR c.id::text ILIKE %s)))")
            params.extend([q_like, q_like, q_like, q_like, q_like, q_like])

        where_sql = " AND ".join(where_clauses)
        offset = (page - 1) * page_size

        # Main SQL includes claims count
        main_sql = f"""
            SELECT
                uf.id::text AS file_id,
                uf.original_filename,
                COALESCE(p.name, 'Unknown') AS payer_name,
                uf.ai_payer_confidence,
                uf.processing_status,
                u.full_name AS reviewer_name,
                uf.uploaded_at,
                COALESCE((SELECT COUNT(1) FROM claims c WHERE c.file_id::text = uf.id::text), 0) AS claims_count
            FROM upload_files uf
            LEFT JOIN payers p ON p.id::text = uf.detected_payer_id::text
            LEFT JOIN users u ON u.id::text = uf.uploaded_by::text
            WHERE {where_sql}
            ORDER BY {mapped_sort} {sort_dir_val}, uf.id DESC
            LIMIT %s OFFSET %s
        """
        params_main = list(params) + [page_size, offset]

        count_sql = f"""
            SELECT COUNT(1) FROM upload_files uf
            LEFT JOIN payers p ON p.id::text = uf.detected_payer_id::text
            LEFT JOIN users u ON u.id::text = uf.uploaded_by::text
            WHERE {where_sql}
        """

        cur = pg.cursor()
        try:
            cur.execute(main_sql, params_main)
            pg_rows = cur.fetchall()

            cur.execute(count_sql, params)
            count_row = cur.fetchone()
            total = int(count_row[0]) if count_row else 0
        finally:
            cur.close()

        if not pg_rows:
            return {
                "tableHeaders": final_headers,
                "tableData": [],
                "pagination": {"total": 0, "page": page, "page_size": page_size},
                "totalRecords": 0,
            }

        # Get latest confidence per file from Mongo
        file_ids = [str(r[0]) for r in pg_rows]
        mongo_pipeline2 = [
            {"$match": {"fileId": {"$in": file_ids}}},
            {"$sort": {"createdAt": -1}},
            {"$group": {"_id": "$fileId", "aiConfidence": {"$first": "$aiConfidence"}, "overallConfidence": {"$first": "$overallConfidence"}}}
        ]
        mongo_docs2 = await db_module.db["extraction_results"].aggregate(mongo_pipeline2).to_list(length=None)
        confidence_lookup: Dict[str, float] = {}
        for doc in mongo_docs2:
            fid = str(doc.get("_id"))
            val = None
            if doc.get("aiConfidence") is not None:
                try:
                    val = float(doc.get("aiConfidence"))
                except Exception:
                    val = None
            elif doc.get("overallConfidence") is not None:
                try:
                    val = float(doc.get("overallConfidence"))
                except Exception:
                    val = None
            if val is not None:
                confidence_lookup[fid] = val

        # Build table rows
        table_rows: List[Dict[str, Any]] = []
        for r in pg_rows:
            fid = str(r[0])
            filename = r[1] or ""
            payer_name = r[2] or "Unknown"
            pg_conf_val = r[3]
            proc_status = r[4] or "Pending Review"
            reviewer_name = r[5] or "Unassigned"
            uploaded_at = r[6]
            claims_count = int(r[7] or 0)

            conf_percent = confidence_lookup.get(fid)
            if conf_percent is None:
                try:
                    conf_percent = float(pg_conf_val) if pg_conf_val is not None else 0.0
                except Exception:
                    conf_percent = 0.0

            if conf_percent >= 90:
                conf_label = "High"
            elif conf_percent >= 80:
                conf_label = "Medium"
            else:
                conf_label = "Low"
            confidence_str = f"{conf_label} {int(round(conf_percent))}%"

            uploaded_str = uploaded_at.strftime("%Y-%m-%d") if isinstance(uploaded_at, (datetime.datetime, datetime.date)) else (str(uploaded_at)[:10] if uploaded_at else None)

            table_rows.append({
                "fileName": filename,
                "payer": payer_name,
                "confidence": confidence_str,
                "status": proc_status,
                "reviewer": reviewer_name,
                "uploaded": uploaded_str,
            })

        # Defensive client-side filtering for payer/name/q if needed
        if payer:
            lower_terms = [t.lower() for t in payer.split(",") if t.strip()]
            table_rows = [rec for rec in table_rows if any(t in (rec["payer"] or "").lower() for t in lower_terms)]

        if q:
            ql = q.lower()
            table_rows = [rec for rec in table_rows if ql in (rec["fileName"] or "").lower() or ql in (rec["payer"] or "").lower() or ql in (rec["status"] or "").lower() or ql in (rec["reviewer"] or "").lower() or ql in (rec["confidence"] or "").lower()]

        total_filtered = len(table_rows)
        table_data = table_rows[:page_size]

        reviewTableData = {"success": "Data fetched successfully",
                            "tableData": {"tableHeaders": final_headers,
                                         "tableData": table_data,
                                         "pagination": {"total": total_filtered, "page": page, "page_size": page_size},
                                         "total_records": total_filtered,}}

        
        return JSONResponse(content=reviewTableData, status_code=200)

    except Exception as exc:
        logger.exception("review_queue error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong while fetching review queue listing data.")