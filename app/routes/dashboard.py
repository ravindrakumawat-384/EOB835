from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from ..services.auth_deps import get_current_user, require_role
import app.common.db.db as db_module
from ..utils.logger import get_logger
from datetime import datetime, timezone
from ..common.db.dashboard_schemas import DashboardResponse
from ..services.pg_upload_files import get_pg_conn
import psycopg2

#log maintainer
logger = get_logger(__name__)


# Router
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

def covert_date_time(value):
    if not value:
        return None
    from datetime import datetime
    try:
        if hasattr(value, "strftime"):
            return value.strftime("%d-%m-%Y")
        dt = datetime.fromisoformat(value.replace("Z", ""))
        return dt.strftime("%d-%m-%Y")
    except:
        return None
    

@router.get("/summary", response_model=DashboardResponse)
async def dashboard_summary() -> JSONResponse:
    """
    Dashboard summary (org-scoped) using upload_batches, upload_files, payers.
    """
    try:
        org_id = "9ac493f7-cc6a-4d7d-8646-affb00ed58da"
        if not org_id:
            raise HTTPException(status_code=400, detail="org_id required in user context")
        # MongoDB stats for accuracy from extraction_results collection
        mongo_accuracy_percent = 0.0
        extraction_col = db_module.db["extraction_results"]
        try:
            # Initialize MongoDB if not already initialized
            if db_module.db is None:
                db_module.init_db()
            
            if db_module.db is not None:
                
                accuracy_pipeline = [
                    {"$match": {"ai_overall_confidence": {"$ne": None, "$exists": True}}},
                    {"$group": {"_id": None, "avg_confidence": {"$avg": "$ai_overall_confidence"}}}
                ]
                acc_result = await extraction_col.aggregate(accuracy_pipeline).to_list(length=1)
                mongo_accuracy_percent = round(acc_result[0]["avg_confidence"], 1) if acc_result else 0.0
        except Exception as e:
            logger.warning(f"MongoDB accuracy calculation failed: {e}")
            mongo_accuracy_percent = 0.0
        
        # Initialize other MongoDB fallback values
        uploaded = 0
        processed = 0
        pending_review = 0
        exceptions = 0
        needs_template = 0
        # PostgreSQL stats
        conn = get_pg_conn()
        cur = conn.cursor()
        # File stats
        cur.execute("SELECT COUNT(*) FROM upload_files WHERE org_id = %s", (org_id,))
        pg_uploaded = cur.fetchone()[0]
       
        # Get count from MongoDB extraction_results collection based on status
        try:
            # extraction_col = db_module.db["extraction_results"]
            
            # Get file_ids for this org from PostgreSQL
            cur.execute("SELECT id FROM upload_files WHERE org_id = %s", (org_id,))
            file_rows = cur.fetchall()
            org_file_ids = [str(r[0]) for r in file_rows] if file_rows else []
            
            if org_file_ids:
                # Count documents with status in ('pending_review', 'completed', 'Ai-Process')
                count_processed = await extraction_col.count_documents({
                    "fileId": {"$in": org_file_ids},
                    "status": {"$in": ['pending_review', 'completed', 'ai-process']}
                })
            else:
                count_processed = 0
        except Exception as e:
            logger.warning(f"MongoDB processed count failed: {e}")
            count_processed = 0
        
        # Get pending_review count from MongoDB extraction_results collection
        try:
            if org_file_ids:
                # Count documents with status 'pending_review'
                pg_pending_review = await extraction_col.count_documents({
                    "fileId": {"$in": org_file_ids},
                    "status": "pending_review"
                })
            else:
                pg_pending_review = 0
        except Exception as e:
            logger.warning(f"MongoDB pending_review count failed: {e}")
            pg_pending_review = 0
        
        try:
            if org_file_ids:
                # Count documents with status in ('failed', 'need_template', 'Unreadable', 'exception')
                exceptions = await extraction_col.count_documents({
                    "fileId": {"$in": org_file_ids},
                    "status": {"$in": ['failed', 'need_template', 'unreadable', 'exception']}
                })
            else:
                exceptions = 0
        except Exception as e:
            logger.warning(f"MongoDB exceptions count failed: {e}")
            exceptions = 0
        
        try:
            if org_file_ids:
                # Count documents with status 'need_template'
                needs_template = await extraction_col.count_documents({
                    "fileId": {"$in": org_file_ids},
                    "status": "need_template"
                })
            else:
                needs_template = 0
        except Exception as e:
            logger.warning(f"MongoDB needs_template count failed: {e}")
            needs_template = 0

        cur.execute("""
            SELECT COUNT(*)
            FROM upload_files
            WHERE org_id = %s
            AND processing_status IN ('failed', 'need_template', 'Unreadable', 'exception')
        """, (org_id,))
        pg_exceptions = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM upload_files WHERE org_id = %s AND processing_status = 'need_template'", (org_id,))
        pg_needs_template = cur.fetchone()[0]
   

        mongo_accuracy_percent = 0.0
        try:

            # Step 1 — fetch file_ids for this org from Postgres
            cur.execute("SELECT id FROM upload_files WHERE org_id = %s", (org_id,))
            file_rows = cur.fetchall()
            file_ids = [str(r[0]) for r in file_rows] if file_rows else []

            if file_ids:
                # Step 2 — fetch matching extraction_results and average aiConfidence
                def split_chunks(lst, n=500):
                    for i in range(0, len(lst), n):
                        yield lst[i:i+n]

                ai_values = []

                for chunk in split_chunks(file_ids):
                    docs = extraction_col.find(
                        {
                            "fileId": {"$in": chunk},
                            "aiConfidence": {"$ne": None}
                        },
                        {"aiConfidence": 1}
                    )

                    results = await docs.to_list(length=500)
                    for d in results:
                        try:
                            ai_values.append(d["aiConfidence"])
                        except:
                            pass

                if ai_values:
                    mongo_accuracy_percent = round(sum(ai_values) / len(ai_values), 1)
                else:
                    mongo_accuracy_percent = 0.0

        except Exception as e:
            logger.warning(f"Mongo org accuracy calculation failed: {e}")
            mongo_accuracy_percent = 0.0
        
        # Additional statistics
        # Template count from templates table
        cur.execute("SELECT COUNT(*) FROM templates WHERE org_id = %s", (org_id,))
        total_templates = cur.fetchone()[0]
        
        # Payer statistics
        cur.execute("SELECT COUNT(*) FROM payers WHERE org_id = %s", (org_id,))
        total_payers = cur.fetchone()[0]
        
        # File type analysis
        cur.execute("""
            SELECT mime_type, COUNT(*) as count
            FROM upload_files 
            WHERE org_id = %s 
            GROUP BY mime_type 
            ORDER BY count DESC 
            LIMIT 5
        """, (org_id,))
        file_types = cur.fetchall()
        
        # Processing time analysis (files processed today)
        cur.execute("""
            SELECT COUNT(*) FROM upload_files 
            WHERE org_id = %s AND DATE(uploaded_at) = CURRENT_DATE
        """, (org_id,))
        files_today = cur.fetchone()[0]
        
        # Claims stats (using JOIN with upload_files since claims doesn't have org_id)
        cur.execute("""
            SELECT COUNT(*) FROM claims c 
            INNER JOIN upload_files uf ON c.file_id = uf.id 
            WHERE uf.org_id = %s
        """, (org_id,))
        total_claims = cur.fetchone()[0]
        cur.execute("""
            SELECT SUM(c.total_paid_amount) FROM claims c 
            INNER JOIN upload_files uf ON c.file_id = uf.id 
            WHERE uf.org_id = %s
        """, (org_id,))
        total_paid = cur.fetchone()[0] or 0.0
        cur.execute("""
            SELECT SUM(c.total_billed_amount) FROM claims c 
            INNER JOIN upload_files uf ON c.file_id = uf.id 
            WHERE uf.org_id = %s
        """, (org_id,))
        total_billed = cur.fetchone()[0] or 0.0
        # 835 exports
        cur.execute("SELECT COUNT(*) FROM exports_835 WHERE org_id = %s", (org_id,))
        total_exports = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM exports_835 WHERE org_id = %s AND status = 'generated'", (org_id,))
        successful_exports = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM exports_835 WHERE org_id = %s AND status = 'error'", (org_id,))
        failed_exports = cur.fetchone()[0]
        # Recent uploads (PostgreSQL) with payer information
        cur.execute("""
            SELECT uf.id, uf.original_filename, uf.uploaded_at, uf.processing_status, 
                   p.name as payer_name, uf.ai_payer_confidence, uf.file_size
            FROM upload_files uf
            LEFT JOIN payers p ON uf.detected_payer_id = p.id
            WHERE uf.org_id = %s 
            ORDER BY uf.uploaded_at DESC 
            LIMIT 10
        """, (org_id,))
        pg_recent = cur.fetchall()
        # Skip MongoDB recent uploads for now (focus on PostgreSQL data)
        def humanize(dt):
            if not dt: return "N/A"
            if isinstance(dt, str):
                try:
                    dt = dt.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt)
                except Exception: return "N/A"
            if not isinstance(dt, datetime):
                try: dt = dt.generation_time
                except Exception: return "N/A"
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            diff = datetime.now(timezone.utc) - dt
            days = diff.days
            secs = diff.seconds
            if days > 0: return f"{days} day{'s' if days > 1 else ''} ago"
            hrs = secs // 3600
            if hrs > 0: return f"{hrs} hour{'s' if hrs > 1 else ''} ago"
            mins = (secs % 3600) // 60
            if mins > 0: return f"{mins} minute{'s' if mins > 1 else ''} ago"
            return "just now"
        table_rows = []
        for row in pg_recent:
            table_rows.append({
                "fileId": str(row[0]),
                "fileName": row[1],
                "payer": row[4] or "Unknown",
                "status": row[3],
                # "uploaded": humanize(row[1])
                "uploaded": covert_date_time(row[2])
            })
        # MongoDB recent uploads removed - using PostgreSQL data only
        resp_data = {
            "success": "Data retrieved successfully",
            "widgets": {
                "uploaded": uploaded + pg_uploaded,
                "processed": count_processed,
                "pendingReview": pending_review + pg_pending_review,
                "accuracyPercent": mongo_accuracy_percent,
                "exceptions": exceptions + pg_exceptions,
                "needsTemplate": needs_template,
            },
            "recentUploadsData": {
                "total_records": 0,
                "tableHeaders": [
                    {"field": "fileName", "label": "File Name"},
                    {"field": "payer", "label": "Payer"},
                    {"field": "status", "label": "Status"},
                    {"field": "uploaded", "label": "Uploaded"},
                    {"label": "Actions", "actions": [{"type": "view", "icon": "pi pi-eye", "styleClass": "p-button-text p-button-sm"}]}
                ],
                "tableData": table_rows
            }
        }
        cur.close()
        conn.close()
        return JSONResponse(content=resp_data, status_code=200)
    except Exception as e:
        logger.error("dashboard summary failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong while fetching dashboard data")

