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
from pydantic import BaseModel

logger = get_logger(__name__)


class UpdateReviewerRequest(BaseModel):
    file_id: str
    reviewer_id: str

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

@router.get("/summary", response_model=None, response_model_exclude_none=True)
# async def review_queue(
#     org_id: str = Query(..., description="organization id (required)"),
#     search: Optional[str] = Query(None, description="Search across filename, claim_id, patient_name, reviewer, payer, status, confidence"),
#     payer: Optional[str] = Query(None, description="payer filter value (supports configured short codes, comma-separated; 'all' = no filter)"),
#     status: Optional[str] = Query(None, description="status filter value (supports configured short codes; 'all' = no filter)"),
#     confidence_cat: Optional[str] = Query(None, alias="confidence", description="High/Medium/Low or 'all'"),
#     page: int = Query(1, ge=1),
#     page_size: int = Query(6, ge=1, le=200),
#     sort_by: str = Query("resolved_uploaded_at"),
#     sort_dir: str = Query("desc"),
# ):
#     try:
#         if not org_id:
#             raise HTTPException(status_code=400, detail={"message": "missing_org_id"})
        
#         if status == "pending":
#             status = "Pending_Review"
#         elif status == "failed":
#             status = "failed"
#         elif status == "warning":
#             status = "warning"
#         elif status == "exception":
#             status = "exception"
#         else:
#             status = status
#         # normalize incoming filters
#         q = (search or "").strip()
#         payer = payer.strip() if payer else None
#         status = status.strip() if status else None
#         confidence_cat = (confidence_cat or "").strip()

#         # sort mapping
#         sort_map = {
#             "fileName": "uf.original_filename",
#             "original_filename": "uf.original_filename",
#             "payer": "p.name",
#             "confidence": "uf.ai_payer_confidence",
#             "status": "uf.processing_status",
#             "reviewer": "u.full_name",
#             "uploaded": "uf.uploaded_at",
#             "resolved_uploaded_at": "uf.uploaded_at",
#         }
#         mapped_sort = sort_map.get(sort_by, "uf.uploaded_at")
#         sort_dir_val = "DESC" if str(sort_dir).lower() == "desc" else "ASC"

#         # obtain a Postgres connection from your project util
#         pg = get_pg_conn()

#         # UI config maps
#         payer_code_map = {
#             "bcbs": "Blue Cross Blue Shield",
#             "aetna": "Aetna",
#             "united": "United Healthcare",
#             "cigna": "Cigna",
#             "medicare": "Medicare",
#             "all": None,
#         }
#         status_code_map = {
#             "pending": "Pending Review",
#             "warning": "Warning",
#             "failed": "Failed Validation",
#             "exception": "Exception",
#             "all": None,
#         }

#         # build reviewer dropdown options
#         cur_opts2 = pg.cursor()
#         try:
#             cur_opts2.execute(
#                 """
#                 SELECT DISTINCT u.id::text, u.full_name
#                 FROM organization_memberships m
#                 JOIN users u ON u.id = m.user_id
#                 WHERE m.org_id = %s AND m.role = 'reviewer'
#                 ORDER BY u.full_name
#                 """,
#                 (org_id,),
#             )
#             reviewer_rows = cur_opts2.fetchall()
#             reviewer_options = [{"label": "Unassigned", "value": "unassigned"}] + [
#                 {"label": rr[1], "value": rr[0]} for rr in reviewer_rows if rr[1]
#             ]
#         finally:
#             cur_opts2.close()

#         final_headers = [
#             {"field": "fileName", "label": "File"},
#             {"field": "payer", "label": "Payer"},
#             {"field": "confidence", "label": "Confidence"},
#             {"field": "status", "label": "Status"},
#             {
#                 "field": "reviewer",
#                 "label": "Reviewer",
#                 "editable": {"type": "dropdown", "placeholder": "Select Reviewer", "options": reviewer_options},
#             },
#             {"field": "uploaded", "label": "Uploaded"},
#             {"label": "Actions", "actions": [{"type": "view", "icon": "pi pi-eye", "styleClass": "p-button-text p-button-sm"}]},
#         ]

#         # -------------------------
#         # 1) CONFIDENCE -> get matching file ids from Mongo (aiConfidence) and restrict SQL by those ids
#         # -------------------------
#         mongo_file_ids: Optional[List[str]] = None
#         if confidence_cat and confidence_cat.lower() != "all":
#             c = confidence_cat.lower()
#             if c == "high":
#                 match_expr = {"$gte": 90}
#             elif c == "medium":
#                 match_expr = {"$gte": 80, "$lt": 90}
#             elif c == "low":
#                 match_expr = {"$lt": 80}
#             else:
#                 match_expr = None

#             if match_expr is not None:
#                 mongo_pipeline = [
#                     {"$match": {"orgId": org_id, "fileId": {"$exists": True}}},
#                     {"$sort": {"createdAt": -1}},
#                     {"$group": {"_id": "$fileId", "aiConfidence": {"$first": "$aiConfidence"}, "overallConfidence": {"$first": "$overallConfidence"}}},
#                     {"$addFields": {"confidence": {"$convert": {"input": {"$ifNull": ["$aiConfidence", "$overallConfidence", 0]}, "to": "double", "onError": 0, "onNull": 0}}}},
#                     {"$match": {"confidence": match_expr}},
#                     {"$project": {"_id": 1}},
#                 ]
#                 mongo_docs = await db_module.db["extraction_results"].aggregate(mongo_pipeline).to_list(length=None)
#                 mongo_file_ids = [str(d["_id"]) for d in mongo_docs]

#                 # If there are no extraction results matching the confidence bucket, return empty set
#                 if not mongo_file_ids:
#                     return JSONResponse(
#                         content={
#                             "tableHeaders": final_headers,
#                             "tableData": [],
#                             "pagination": {"total": 0, "page": page, "page_size": page_size},
#                             "totalRecords": 0,
#                         },
#                         status_code=200,
#                     )

#         # -------------------------
#         # 2) BUILD SQL WHERE CLAUSES FOR upload_files
#         # -------------------------
#         where_clauses = ["uf.org_id = %s"]
#         params: List[Any] = [org_id]

#         # status filter using status_code_map; support comma-separated values; 'all' or None means no filter
#         if status and status.lower() != "all":
#             terms = [s.strip() for s in status.split(",") if s.strip()]
#             status_sub = []
#             for t in terms:
#                 t_low = t.lower()
#                 mapped = status_code_map.get(t_low)
#                 if mapped:
#                     # exact match (case-insensitive)
#                     status_sub.append("uf.processing_status ILIKE %s")
#                     params.append(mapped)
#                 else:
#                     # direct DB search for provided text (case-insensitive exact)
#                     status_sub.append("uf.processing_status ILIKE %s")
#                     params.append(t)
#             if status_sub:
#                 where_clauses.append("(" + " OR ".join(status_sub) + ")")

#         # payer filter: support short codes, names, comma-separated; 'all' means no filter
#         if payer and payer.lower() != "all":
#             terms = [p.strip() for p in payer.split(",") if p.strip()]
#             payer_sub = []
#             for t in terms:
#                 t_low = t.lower()
#                 if t_low in payer_code_map and payer_code_map[t_low]:
#                     payer_sub.append("p.name ILIKE %s")
#                     params.append(f"%{payer_code_map[t_low]}%")
#                 else:
#                     payer_sub.append("p.id::text = %s")
#                     params.append(t)
#                     payer_sub.append("p.name ILIKE %s")
#                     params.append(f"%{t}%")
#             where_clauses.append("(" + " OR ".join(payer_sub) + ")")

#         # if confidence-driven mongo_file_ids exist, restrict upload_files by them
#         if mongo_file_ids is not None:
#             placeholders = ",".join(["%s"] * len(mongo_file_ids))
#             where_clauses.append(f"uf.id::text IN ({placeholders})")
#             params.extend(mongo_file_ids)

#         # q search across filename, payer name, reviewer name, processing_status
#         if q:
#             q_like = f"%{q}%"
#             where_clauses.append(
#                 "("
#                 "uf.original_filename ILIKE %s OR "
#                 "p.name ILIKE %s OR "
#                 "u.full_name ILIKE %s OR "
#                 "uf.processing_status ILIKE %s"
#                 ")"
#             )
#             params.extend([q_like, q_like, q_like, q_like])

#         where_sql = " AND ".join(where_clauses)
#         offset = (page - 1) * page_size

#         main_sql = f"""
#             SELECT
#                 uf.id::text AS file_id,
#                 uf.original_filename,
#                 COALESCE(p.name, 'Unknown') AS payer_name,
#                 uf.ai_payer_confidence,
#                 uf.processing_status,
#                 uf.reviwer_id AS reviewer_id,
#                 uf.uploaded_at
#             FROM upload_files uf
#             LEFT JOIN payers p ON p.id::text = uf.detected_payer_id::text
#             LEFT JOIN users u ON u.id::text = uf.reviwer_id::text
#             WHERE {where_sql}
#             ORDER BY {mapped_sort} {sort_dir_val}, uf.id DESC
#             LIMIT %s OFFSET %s
#         """
#         params_main = list(params) + [page_size, offset]

#         count_sql = f"""
#             SELECT COUNT(1) FROM upload_files uf
#             LEFT JOIN payers p ON p.id::text = uf.detected_payer_id::text
#             LEFT JOIN users u ON u.id::text = uf.reviwer_id::text
#             WHERE {where_sql}
#         """

#         cur = pg.cursor()
#         try:
#             cur.execute(main_sql, params_main)
#             pg_rows = cur.fetchall()

#             cur.execute(count_sql, params)
#             count_row = cur.fetchone()
#             total_sql_count = int(count_row[0]) if count_row else 0
#         finally:
#             cur.close()

#         if not pg_rows:
#             reviewTableData = {
#                 "success": "No Data Found.",
    
#                 "tableData": {
#                     "tableHeaders": final_headers,
#                     "tableData": [],
#                     "pagination": {"total": 0, "page": page, "page_size": page_size},
#                     "total_records": 0,
#                 },
#             }
#             return JSONResponse(content=reviewTableData, status_code=200)
         

#         # -------------------------
#         # 3) For returned upload_files, get latest extraction (confidence + payerName) from Mongo
#         # -------------------------
#         file_ids = [str(r[0]) for r in pg_rows]
#         mongo_pipeline2 = [
#             {"$match": {"fileId": {"$in": file_ids}, "orgId": org_id}},
#             {"$sort": {"createdAt": -1}},
#             {"$group": {"_id": "$fileId", "aiConfidence": {"$first": "$aiConfidence"}, "overallConfidence": {"$first": "$overallConfidence"}, "payerName": {"$first": "$payerName"}}},
#         ]
#         mongo_docs2 = await db_module.db["extraction_results"].aggregate(mongo_pipeline2).to_list(length=None)
#         confidence_lookup: Dict[str, float] = {}
#         payer_lookup: Dict[str, str] = {}
#         for doc in mongo_docs2:
#             fid = str(doc.get("_id"))
#             payer_lookup[fid] = doc.get("payerName") or "Unknown"
#             val = None
#             if doc.get("aiConfidence") is not None:
#                 try:
#                     val = float(doc.get("aiConfidence"))
#                 except Exception:
#                     val = None
#             if val is None and doc.get("overallConfidence") is not None:
#                 try:
#                     val = float(doc.get("overallConfidence"))
#                 except Exception:
#                     val = None
#             if val is not None:
#                 confidence_lookup[fid] = val

#         # -------------------------
#         # 4) Build table rows
#         # -------------------------
#         table_rows: List[Dict[str, Any]] = []
#         for r in pg_rows:
#             fid = str(r[0])
#             filename = r[1] or ""
#             payer_name = payer_lookup.get(fid, r[2] or "Unknown")
#             pg_conf_val = r[3]
#             proc_status = r[4] or "Pending Review"
#             reviewer_name = r[5] or "unassigned"
#             uploaded_at = r[6]

#             conf_percent = confidence_lookup.get(fid)
#             print("conf_percent======",conf_percent)
#             if conf_percent is None:
#                 try:
#                     conf_percent = float(pg_conf_val) if pg_conf_val is not None else 0.0
#                 except Exception:
#                     conf_percent = 0.0

#             if conf_percent >= 90:
#                 conf_label = "High"
#             elif conf_percent >= 80:
#                 conf_label = "Medium"
#             else:
#                 conf_label = "Low"
#             confidence_str = f"{int(round(conf_percent))}%"

#             uploaded_str = uploaded_at.strftime("%Y-%m-%d") if isinstance(uploaded_at, (datetime.datetime, datetime.date)) else (str(uploaded_at)[:10] if uploaded_at else None)

#             table_rows.append({
#                 "file_id": fid,
#                 "fileName": filename,
#                 "payer": payer_name,
#                 "confidence": confidence_str,
#                 "status": proc_status,
#                 "reviewer": reviewer_name,
#                 "uploaded": uploaded_str,
#             })

#         # final response uses server-side COUNT and rows
#         reviewTableData = {
#             "success": "Data fetched successfully",
#             # "tableHeaders": final_headers,
#             "tableData": {
#                 "tableHeaders": final_headers,
#                 "tableData": table_rows,
#                 "pagination": {"total": total_sql_count, "page": page, "page_size": page_size},
#                 "total_records": total_sql_count,
#             },
#         }

#         return JSONResponse(content=reviewTableData, status_code=200)

#     except Exception as exc:
#         import logging

#         logging.exception("review_queue error: %s", exc, exc_info=True)
#         raise HTTPException(status_code=500, detail="Something went wrong while fetching review queue listing data.")


@router.get("/summary", response_model_exclude_none=True)
async def review_queue(
    org_id: str = Query(...),
    search: Optional[str] = Query(None),
    payer: Optional[str] = Query("all"),
    status: Optional[str] = Query("all"),
    confidence_cat: Optional[str] = Query("all"),
    # confidence_cat: Optional[str] = Query("all", alias="confidence"),
    page: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=1000),
):
    # try:
    pg = get_pg_conn()

    if status == "pending":
        status = "pending_review"

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

    if status != "all":
        where.append("uf.processing_status ILIKE %s")
        params.append(status)

    if payer != "all":
        where.append("p.name ILIKE %s")
        params.append(f"%{payer}%")

    if search:
        q = f"%{search}%"
        where.append(
            """
            (
                uf.original_filename ILIKE %s OR
                p.name ILIKE %s OR
                uf.processing_status ILIKE %s OR
                u.full_name ILIKE %s
            )
            """
        )
        params.extend([q, q, q, q])

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

    mongo_docs = await db_module.db["extraction_results"].find(
        {"fileId": {"$in": mongo_file_ids}}
    ).to_list(length=None)

    extraction_map = {}
    for d in mongo_docs:
        fid = d["fileId"].replace("store", "")
        extraction_map.setdefault(fid, []).append(d)

    # ---------------------------
    # BUILD ALL ROWS FIRST
    # ---------------------------
    table_rows = []

    for r in pg_rows:
        file_id, filename, payer_name, status_val, reviewer_id, uploaded_at = r
        extractions = extraction_map.get(file_id, [])

        for ext in extractions:
            conf_val = float(ext.get("totalExtractedAmount") or 0)

            if confidence_cat != "all":
                if confidence_cat == "high" and conf_val < 90:
                    continue
                if confidence_cat == "medium" and not (80 <= conf_val < 90):
                    continue
                if confidence_cat == "low" and conf_val >= 80:
                    continue

            table_rows.append(
                {
                    "fileName": filename,
                    "payer": ext.get("payerName") or payer_name or "Unknown",
                    "confidence": f"{int(conf_val)}%",
                    "status": status_val,
                    "reviewer": reviewer_id or "Unassigned",
                    "uploaded": uploaded_at.strftime("%Y-%m-%d"),
                }
            )

    # ---------------------------
    # ✅ FIXED PAGINATION (ONLY CHANGE)
    # ---------------------------
    total_records = len(table_rows)

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

    # except Exception:
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Something went wrong while fetching review queue data",
    #     )




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
            (payload.reviewer_id, payload.file_id),
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
