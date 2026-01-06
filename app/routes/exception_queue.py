from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.common.db.pg_db import get_pg_conn
import app.common.db.db as db_module
import psycopg2.extras
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger
from datetime import datetime


router = APIRouter(prefix="/exception-queue", tags=["exception-queue"])
logger = get_logger(__name__)


@router.get("/files", response_model=Dict[str, Any])
async def get_exception_files(
    user: Dict[str, Any] = Depends(get_current_user),
    search: Optional[str] = Query(None, description="Search by file name, error type, or description"),
    exception_type: Optional[str] = Query("all", description="Filter by exception type"),
    # date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    # date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=1000),
):
    """Get Exception Queue data for the current user's organization."""
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

                # Base query - include both a camelCase alias and original column name to support callers
                query = """
                    SELECT
                        uf.id::text AS id,
                        uf.original_filename AS fileName,
                        uf.original_filename AS original_filename,
                        COALESCE(p.name, '') AS payer,
                        uf.processing_error_message AS description,
                        to_char(uf.uploaded_at, 'YYYY-MM-DD') AS date
                    FROM upload_files uf
                    LEFT JOIN payers p ON p.id = uf.detected_payer_id
                    WHERE uf.org_id = %s AND (uf.processing_status = 'exception' OR uf.processing_error_message IS NOT NULL)
                """
                params = [org_id]

                # Optional search on filename/description
                if search:
                    query += " AND (uf.original_filename ILIKE %s OR uf.processing_error_message ILIKE %s OR p.name ILIKE %s)"
                    params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

                query += " ORDER BY uf.uploaded_at DESC LIMIT 1000"
                cur.execute(query, tuple(params))
                files = cur.fetchall()

        # helper to map description to a short exception type code
        def map_exception_type(desc: Optional[str]) -> str:
            if not desc:
                return "unknown"
            d = desc.lower()
            if "template" in d:
                return "needs_template"
            if "ocr" in d or "ocr failed" in d:
                return "ocr_error"
            if "unmapped" in d or "payer detected" in d:
                return "unmapped_payer"
            if "password" in d or "corrupt" in d or "corrupted" in d:
                return "unreadable_pdf"
            return "other"

        # Build table data
        table_data = []
        for f in files:
            exc_desc = f.get("description") or ""
            exc_type = map_exception_type(exc_desc)
            # Ensure filename is available under both keys
            filename = f.get("fileName") or f.get("original_filename") or ""
            table_data.append({
                "file_id": f.get("id"),
                "fileName": filename,
                "payer": f.get("payer") or "-",
                "exceptionType": exc_type,
                "description": exc_desc or "-",
                "date": f.get("date") or "-",
                "actions": {
                    "view_url": f"/exception-queue/files/{f.get('id')}/view",
                    "download_url": f"/exception-queue/files/{f.get('id')}/download"
                }
            })

        # Apply exception_type filter (client can pass 'all' or specific code)
        filtered = []
        s = (search or "").lower()
        for r in table_data:
            if exception_type and exception_type != "all":
                if r.get("exceptionType") != exception_type:
                    continue
            # date filters
            # if date_from and r.get("date") < date_from:
            #     continue
            # if date_to and r.get("date") > date_to:
            #     continue
            # search already applied in SQL, but keep additional safety
            if search and s not in f"{r.get('fileName','')} {r.get('payer','')} {r.get('exceptionType','')} {r.get('description','') }".lower():
                continue
            filtered.append(r)

        total_records = len(filtered)
        total_pages = (total_records + page_size - 1) // page_size
        if page > total_pages and total_pages > 0:
            page = total_pages
        start = (page - 1) * page_size
        end = start + page_size
        page_rows = filtered[start:end]

        table_headers = [
            {"field": "fileName", "label": "File Name"},
            {"field": "payer", "label": "Payer"},
            {"field": "exceptionType", "label": "Exception Type", "mutlicell": True},
            {"field": "description", "label": "Description"},
            {"field": "date", "label": "Date", "isDate": True},
            
            {"label": "Actions"},
        ]

        return {
            "tableData": {
                "tableHeaders": table_headers,
                "tableData": page_rows,
                "pagination": {"total": total_records, "page": page, "page_size": page_size},
                "total_records": total_records,
            },
            "success": "Exception queue data loaded successfully",
        }
    except Exception as e:
        logger.error(f"Failed to fetch Exception Queue data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch Exception Queue data")


# View/Download endpoints for exception queue files
@router.get("/files/{file_id}/view")
async def view_exception_file(file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Return a presigned URL suitable for viewing the file (inline)."""
    try:
        user_id = user.get("id")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_id = org["org_id"]

                cur.execute("SELECT id::text AS id, storage_path, original_filename, org_id FROM upload_files WHERE id = %s LIMIT 1", (file_id,))
                file_row = cur.fetchone()
                if not file_row or not file_row.get("storage_path"):
                    raise HTTPException(status_code=404, detail="File not found")
                if file_row.get("org_id") != org_id:
                    raise HTTPException(status_code=403, detail="Forbidden")

        from app.services.s3_service import S3Service
        from app.common.config import settings
        s3_service = S3Service(
            settings.S3_BUCKET,
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_REGION,
        )
        presigned_url = s3_service.generate_presigned_image_url(file_row["storage_path"]) if file_row.get("storage_path") else None
        if not presigned_url:
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
async def download_exception_file(file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Return a presigned URL for downloading the file (attachment)."""
    try:
        user_id = user.get("id")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_id = org["org_id"]

                cur.execute("SELECT id::text AS id, storage_path, original_filename, org_id FROM upload_files WHERE id = %s LIMIT 1", (file_id,))
                file_row = cur.fetchone()
                if not file_row or not file_row.get("storage_path"):
                    raise HTTPException(status_code=404, detail="File not found")
                if file_row.get("org_id") != org_id:
                    raise HTTPException(status_code=403, detail="Forbidden")

        from app.services.s3_service import S3Service
        from app.common.config import settings
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


