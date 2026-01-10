from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.common.db.pg_db import get_pg_conn
import app.common.db.db as db_module
import psycopg2.extras
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger
from datetime import datetime
from app.services.s3_service import S3Service
from app.common.config import settings

router = APIRouter(prefix="/eob-history", tags=["eob-history"])
logger = get_logger(__name__)


@router.get("/get_eob_history", response_model=Dict[str, Any])
async def get_eob_history(
    user: Dict[str, Any] = Depends(get_current_user),
    search: Optional[str] = Query(None),
    payer: Optional[str] = Query("all"),
    status: Optional[str] = Query("all"),
    sort_by: Optional[str] = Query("date"),
    sort_dir: Optional[str] = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=1000),
):
    """Get EOB history data for current user's organization"""
    try:
        user_id = user.get("id")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get org_id for current user
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_id = org["org_id"]

                # Fetch upload files
                cur.execute(
                    """
                    SELECT uf.id::text AS id, uf.original_filename, uf.processing_status, uf.uploaded_at, p.name AS payer_name
                    FROM upload_files uf
                    LEFT JOIN payers p ON p.id = uf.detected_payer_id
                    WHERE uf.org_id = %s
                    ORDER BY uf.uploaded_at DESC
                    LIMIT 1000
                    """,
                    (org_id,)
                )
                files = cur.fetchall()

                # Fetch list of payers for this org to return for UI filters
                cur.execute(
                    """
                    SELECT id::text AS id, name
                    FROM payers
                    WHERE org_id = %s
                    ORDER BY name
                    """,
                    (org_id,)
                )
                payer_rows = cur.fetchall()
                payer_list = [{"label": "All Payers", "value": "all"}] + [
                    {"label": r.get("name") if isinstance(r, dict) else r[1], "value": r.get("name") if isinstance(r, dict) else r[1]} for r in payer_rows
                ]

        # If no files, return empty structure
        if not files:
            table_headers = [
                {"field": "fileName", "label": "File Name", "isSortable": True},
                {"field": "payer", "label": "Payer", "isSortable": True},
                {"field": "claimCount", "label": "Claims", "isSortable": True},
                {"field": "date", "label": "Date", "isDate": True, "isSortable": True},
                {"field": "status", "label": "Status", "isSortable": True},
                {"field": "actions", "label": "Actions"},
            ]
            return {
                "message": "EOB History data fetched successfully.",
                "tableData": {
                    "tableHeaders": table_headers,
                    "tableData": [],
                    "pagination": {"total": 0, "page": page, "page_size": page_size},
                    "total_records": 0,
                },
            }

        # Query MongoDB for extraction results for these files
        file_ids = [f["id"] for f in files]
        mongo_docs = await db_module.db["extraction_results"].find({"fileId": {"$in": file_ids}}).to_list(length=None)

        # Group extractions by fileId
        extractions_by_file = {}
        for d in mongo_docs:
            fid = d.get("fileId")
            extractions_by_file.setdefault(fid, []).append(d)

        rows = []
        for f in files:
            fid = f["id"]
            filename = f.get("original_filename")
            payer_name = f.get("payer_name")
            uploaded_at = f.get("uploaded_at")
            file_status = f.get("processing_status")

            exts = extractions_by_file.get(fid, [])
            
            # Get first extraction data for display (file level)
            claim_count = len(exts)
            first_ext = exts[0] if exts else None
            
            ext_payer = first_ext.get("payerName") if first_ext else payer_name
            ext_status = first_ext.get("status") if first_ext else file_status
            patient = first_ext.get("patientName") or first_ext.get("patient_name") if first_ext else None
            
            date_str = None
            if uploaded_at:
                try:
                    date_str = uploaded_at.strftime("%Y-%m-%d")
                except Exception:
                    date_str = str(uploaded_at)

            rows.append({
                "id": fid,
                "fileName": filename,
                "payer": ext_payer or payer_name or "-",
                "claimCount": claim_count,
                "date": date_str or "-",
                "uploaded_at": uploaded_at,  # Keep original for sorting
                "status": ext_status or file_status or "-",
                "actions": {
                    "view_url": f"/eob-history/files/{fid}/view",
                    "download_url": f"/eob-history/files/{fid}/download"
                }
            })

        # Apply filters
        filtered = []
        s = (search or "").lower()
        for r in rows:
            if search:
                hay = f"{r.get('fileName','')} {r.get('payer','')} {r.get('status','')}".lower()
                if s not in hay:
                    continue
            if payer and payer != "all":
                if not r.get("payer") or payer.lower() not in r.get("payer").lower():
                    continue
            if status and status != "all":
                if r.get("status") != status:
                    continue
            filtered.append(r)

        # Apply sorting
        valid_sort_fields = ["fileName", "payer", "claimCount", "date", "status"]
        print(f"DEBUG: sort_by={sort_by}, sort_dir={sort_dir}, valid={sort_by in valid_sort_fields}")
        if sort_by in valid_sort_fields:
            reverse = sort_dir.lower() == "desc"
            print(f"DEBUG: Sorting by {sort_by}, reverse={reverse}")
            if sort_by == "date":
                filtered.sort(
                    key=lambda x: x.get("uploaded_at") or datetime(1900, 1, 1),
                    reverse=reverse
                )
            elif sort_by == "claimCount":
                filtered.sort(
                    key=lambda x: x.get("claimCount", 0),
                    reverse=reverse
                )
            elif sort_by == "status":
                status_priority = {
                    "pending_review": 1,
                    "ai_processing": 2,
                    "in_review": 3,
                    "approved": 4,
                    "rejected": 5,
                    "failed": 6,
                }
                filtered.sort(
                    key=lambda x: (
                        status_priority.get(x.get("status", ""), 99),
                        (x.get("status") or "").lower()
                    ),
                    reverse=reverse
                )
            else:
                filtered.sort(
                    key=lambda x: (x.get(sort_by) or "").lower(),
                    reverse=reverse
                )

        total_records = len(filtered)
        total_pages = (total_records + page_size - 1) // page_size
        if page > total_pages and total_pages > 0:
            page = total_pages
        start = (page - 1) * page_size
        end = start + page_size
        page_rows = filtered[start:end]

        table_headers = [
            {"field": "fileName", "label": "File Name", "isSortable": True},
            {"field": "payer", "label": "Payer", "isSortable": True},
            {"field": "claimCount", "label": "Claims", "isSortable": True},
            {"field": "date", "label": "Date", "isDate": True, "isSortable": True},
            {"field": "status", "label": "Status", "isSortable": False},
            {"label": "Actions"},
        ]

        return {
            "message": "EOB History data fetched successfully.",
            "tableData": {
                "tableHeaders": table_headers,
                "tableData": page_rows,
                "pagination": {"total": total_records, "page": page, "page_size": page_size},
                "total_records": total_records,
            },
            'payer_list':payer_list,
        }
    except Exception as e:
        logger.exception("Failed to fetch EOB history: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch EOB history data")


@router.get("/files/{file_id}/view")
async def view_eob_file(file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Return a presigned URL suitable for viewing the file (inline)."""
    try:
        user_id = user.get("id")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Verify user's organization
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_id = org["org_id"]

                # Get file record
                cur.execute("SELECT id::text AS id, storage_path, original_filename, org_id FROM upload_files WHERE id = %s LIMIT 1", (file_id,))
                file_row = cur.fetchone()
                if not file_row or not file_row.get("storage_path"):
                    raise HTTPException(status_code=404, detail="File not found")
                if file_row.get("org_id") != org_id:
                    raise HTTPException(status_code=403, detail="Forbidden")

        s3_service = S3Service(
            settings.S3_BUCKET,
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_REGION,
        )
        presigned_url = s3_service.generate_presigned_image_url(file_row["storage_path"]) if file_row.get("storage_path") else None
        if not presigned_url:
            # fallback to generic presigned URL
            presigned_url = s3_service.generate_presigned_url(file_row["storage_path"], expiration=300)

        if not presigned_url:
            raise HTTPException(status_code=500, detail="Failed to generate file view URL")

        return {"view_url": presigned_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate view URL: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate file view URL")


@router.get("/files/{file_id}/download")
async def download_eob_file(file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Return a presigned URL for downloading the file (attachment)."""
    try:
        user_id = user.get("id")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Verify user's organization
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_id = org["org_id"]

                # Get file record
                cur.execute("SELECT id::text AS id, storage_path, original_filename, org_id FROM upload_files WHERE id = %s LIMIT 1", (file_id,))
                file_row = cur.fetchone()
                if not file_row or not file_row.get("storage_path"):
                    raise HTTPException(status_code=404, detail="File not found")
                if file_row.get("org_id") != org_id:
                    raise HTTPException(status_code=403, detail="Forbidden")

        s3_service = S3Service(
            settings.S3_BUCKET,
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_REGION,
        )
        filename = file_row.get("original_filename") or "download"
        disposition = f'attachment; filename="{filename}"'
        presigned_url = s3_service.generate_presigned_url(file_row["storage_path"], expiration=300, response_content_disposition=disposition)
        if not presigned_url:
            raise HTTPException(status_code=500, detail="Failed to generate file download URL")

        return {"download_url": presigned_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate download URL: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate file download URL")


