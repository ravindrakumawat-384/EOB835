from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.common.db.pg_db import get_pg_conn
import psycopg2.extras
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger
from datetime import datetime

router = APIRouter(prefix="/eob-history", tags=["eob-history"])
logger = get_logger(__name__)

# GET /eob-history/files
@router.get("/files", response_model=List[Dict[str, Any]])
async def get_eob_files(
	user: Dict[str, Any] = Depends(get_current_user),
	file_name: Optional[str] = Query(None, description="Filter by file name"),
	payer: Optional[str] = Query(None, description="Filter by payer name"),
	status: Optional[str] = Query(None, description="Filter by status"),
	date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
	date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
	"""
	Get EOB file history for the current user's organization.
	Returns a list of files with metadata for frontend display.
	"""
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

				# Build query with joins for all required fields
				query = """
					SELECT
						uf.id AS id,
						uf.original_filename AS fileName,
						uf.mime_type AS fileType,
						COALESCE(p.name, '') AS payer,
						COALESCE(c.claim_number, '') AS claimId,
						COALESCE(pay.payment_reference, '') AS checkNumber,
						COALESCE(c.patient_name, '') AS patient,
						to_char(uf.uploaded_at, 'YYYY-MM-DD') AS date,
						uf.processing_status AS status
					FROM upload_files uf
					LEFT JOIN payments pay ON pay.file_id = uf.id
					LEFT JOIN claims c ON c.file_id = uf.id
					LEFT JOIN payers p ON p.id = pay.payer_id
					WHERE uf.org_id = %s
				"""
				params = [org_id]
				if file_name:
					query += " AND uf.original_filename ILIKE %s"
					params.append(f"%{file_name}%")
				if status:
					query += " AND uf.processing_status = %s"
					params.append(status)
				if date_from:
					query += " AND uf.uploaded_at >= %s"
					params.append(date_from)
				if date_to:
					query += " AND uf.uploaded_at <= %s"
					params.append(date_to)

				query += " ORDER BY uf.uploaded_at DESC LIMIT 100"
				cur.execute(query, tuple(params))
				files = cur.fetchall()
				
                # Add view/download URLs for Actions
				for f in files:
					file_id = f["id"]
					f["actions"] = {
						"view_url": f"/eob-history/files/{file_id}/view",
						"download_url": f"/eob-history/files/{file_id}/download"
					}

		# Table headers as per frontend spec
		table_headers = [
			{"field": "fileName", "label": "File Name"},
			{"field": "fileType", "label": "Type"},
			{"field": "payer", "label": "Payer"},
			{"field": "claimId", "label": "Claim ID"},
			{"field": "checkNumber", "label": "Check #"},
			{"field": "patient", "label": "Patient"},
			{"field": "date", "label": "Date", "isDate": True},
			{"field": "status", "label": "Status"},
			# {"label": "Actions"},
			{"field": "actions", "label": "Actions"},
		]

		# Pagination (static for now, can be made dynamic)
		page = 1
		page_size = 10
		total_records = len(files)
		pagination = {
			"total": total_records,
			"page": page,
			"page_size": page_size,
		}

		response = {
			"message": "EOB History data fetched successfully.",
			"tableData": {
				"tableHeaders": table_headers,
				"tableData": files,
				"pagination": pagination,
				"total_records": total_records,
			},
		}
		return response
	except Exception as e:
		logger.error(f"Failed to fetch EOB file history: {e}")
		raise HTTPException(status_code=500, detail="Failed to fetch EOB file history")


# View EOB file (returns presigned S3 URL or file preview)
@router.get("/files/{file_id}/view")
async def view_eob_file(file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns a presigned S3 URL for viewing the EOB file (PDF or X12).
    """
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT storage_path FROM upload_files WHERE id = %s LIMIT 1", (file_id,))
                file_row = cur.fetchone()
        if not file_row or not file_row.get("storage_path"):
            raise HTTPException(status_code=404, detail="File not found")
        # Generate presigned S3 URL (assume S3Service is available)
        from app.services.s3_service import S3Service
        from app.common.config import settings
        s3_service = S3Service(
            settings.S3_BUCKET,
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_REGION
        )
        presigned_url = s3_service.generate_presigned_image_url(file_row["storage_path"])
        if not presigned_url:
            raise HTTPException(status_code=500, detail="Failed to generate file view URL")
        return {"view_url": presigned_url}
    except Exception as e:
        logger.error(f"Failed to generate file view URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate file view URL")


# Download EOB file (returns presigned S3 download URL)
@router.get("/files/{file_id}/download")
async def download_eob_file(file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns a presigned S3 URL for downloading the EOB file.
    """
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT storage_path FROM upload_files WHERE id = %s LIMIT 1", (file_id,))
                file_row = cur.fetchone()
        if not file_row or not file_row.get("storage_path"):
            raise HTTPException(status_code=404, detail="File not found")
        # Generate presigned S3 URL (assume S3Service is available)
        from app.services.s3_service import S3Service
        from app.common.config import settings
        s3_service = S3Service(
            settings.S3_BUCKET,
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_REGION
        )
        presigned_url = s3_service.generate_presigned_image_url(file_row["storage_path"], response_content_disposition="attachment")
        if not presigned_url:
            raise HTTPException(status_code=500, detail="Failed to generate file download URL")
        return {"download_url": presigned_url}
    except Exception as e:
        logger.error(f"Failed to generate file download URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate file download URL")