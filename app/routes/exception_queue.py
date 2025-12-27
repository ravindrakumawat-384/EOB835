from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.common.db.pg_db import get_pg_conn
import psycopg2.extras
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger
from datetime import datetime

router = APIRouter(prefix="/exception-queue", tags=["exception-queue"])
logger = get_logger(__name__)

# GET /exception-queue/files
@router.get("/files", response_model=Dict[str, Any])
async def get_exception_files(
	user: Dict[str, Any] = Depends(get_current_user),
	file_name: Optional[str] = Query(None, description="Filter by file name"),
	exception_type: Optional[str] = Query(None, description="Filter by exception type"),
	date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
	date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
	"""
	Get Exception Queue data for the current user's organization.
	Returns a list of files with exception metadata for frontend display.
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

				# Build query for exception files (example: status = 'exception' or processing_error_message is not null)
				query = """
					SELECT
						uf.id AS id,
						uf.original_filename AS fileName,
						COALESCE(p.name, '') AS payer,
						uf.processing_error_message AS exceptionType,
						uf.processing_error_message AS description,
						to_char(uf.uploaded_at, 'YYYY-MM-DD') AS date
					FROM upload_files uf
					LEFT JOIN payers p ON p.id = uf.detected_payer_id
					WHERE uf.org_id = %s AND (uf.processing_status = 'exception' OR uf.processing_error_message IS NOT NULL)
				"""
				params = [org_id]
				if file_name:
					query += " AND uf.original_filename ILIKE %s"
					params.append(f"%{file_name}%")
				if exception_type:
					query += " AND uf.processing_error_message ILIKE %s"
					params.append(f"%{exception_type}%")
				if date_from:
					query += " AND uf.uploaded_at >= %s"
					params.append(date_from)
				if date_to:
					query += " AND uf.uploaded_at <= %s"
					params.append(date_to)

				query += " ORDER BY uf.uploaded_at DESC LIMIT 100"
				cur.execute(query, tuple(params))
				files = cur.fetchall()

		# Table headers as per frontend spec
		table_headers = [
			{"field": "fileName", "label": "File Name"},
			{"field": "payer", "label": "Payer"},
			{"field": "exceptionType", "label": "Exception Type"},
			{"field": "description", "label": "Description"},
			{"field": "date", "label": "Date"},
			{"label": "Actions"},
		]

		# Format tableData as per frontend spec
		table_data = []
		for f in files:
			table_data.append({
				"file_id": f["id"],
				"fileName": f["fileName"],
				"payer": f["payer"],
				"exceptionType": f["exceptionType"],
				"description": f["description"],
				"date": f["date"],
			})

		# Pagination (static for now)
		page = 1
		page_size = 10
		total_records = len(table_data)
		pagination = {
			"total": total_records,
			"page": page,
			"page_size": page_size,
		}

		response = {
			"tableData": {
				"tableHeaders": table_headers,
				"tableData": table_data,
				"pagination": pagination,
				"total_records": total_records,
			},
			"success": "Exception queue data loaded successfully",
		}
		return response
	except Exception as e:
		logger.error(f"Failed to fetch Exception Queue data: {e}")
		raise HTTPException(status_code=500, detail="Failed to fetch Exception Queue data")
