from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from ..services.auth_deps import get_current_user, require_role
import app.common.db.db as db_module
from ..utils.logger import get_logger
from datetime import datetime, timezone
from ..common.db.dashboard_schemas import DashboardResponse
# from ..services.pg_upload_files import get_pg_conn
from app.common.db.pg_db import get_pg_conn
from ..services.auth_deps import get_current_user, require_role
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
async def dashboard_summary(user: Dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """
    Dashboard summary (org-scoped) using upload_batches, upload_files, payers.
    """
    try:
        user_id = user.get("id")
        print('user_id==================', user_id)
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""SELECT org_id, role FROM organization_memberships WHERE user_id = %s LIMIT 1
                """, (user_id,))
        membership = cur.fetchone()
        print("membership==================", membership)
        org_id = membership[0]
        user_role = membership[1]
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
        # conn = get_pg_conn()
        # cur = conn.cursor()
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
                    "status": {"$in": ['pending_review', 'approved', 'ai-process']}
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
                    "status": {"$in": ['failed', 'unreadable', 'exception']}
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
            AND processing_status IN ('failed','Unreadable', 'exception', 'need_template')
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
        # Recent uploads (PostgreSQL) with payer information and MongoDB extraction data
        role = user_role.lower()
        if role == "reviewer":
            cur.execute("""
                SELECT uf.id, uf.original_filename, uf.uploaded_at, uf.processing_status, 
                   p.name as payer_name, uf.ai_payer_confidence, uf.file_size, uf.reviwer_id
                FROM upload_files uf
                LEFT JOIN payers p ON uf.detected_payer_id = p.id
                WHERE uf.org_id = %s 
                AND uf.reviwer_id = %s
                ORDER BY uf.uploaded_at DESC 
                LIMIT 10
            """, (org_id, user_id))
        else:
            cur.execute("""
                SELECT uf.id, uf.original_filename, uf.uploaded_at, uf.processing_status, 
                   p.name as payer_name, uf.ai_payer_confidence, uf.file_size, uf.reviwer_id
                FROM upload_files uf
                LEFT JOIN payers p ON uf.detected_payer_id = p.id
                WHERE uf.org_id = %s 
                ORDER BY uf.uploaded_at DESC 
                LIMIT 10
            """, (org_id,))
        pg_recent = cur.fetchall()
        
        # Fetch extraction data for recent uploads
        recent_file_ids = [str(r[0]) for r in pg_recent] if pg_recent else []
        extraction_data_map = {}
        
        if recent_file_ids:
            try:
                extraction_docs = await extraction_col.find(
                    {"fileId": {"$in": recent_file_ids}}
                ).to_list(length=None)
                
                for doc in extraction_docs:
                    file_id = doc.get("fileId", "").replace("store", "")
                    if file_id not in extraction_data_map:
                        extraction_data_map[file_id] = []
                    extraction_data_map[file_id].append(doc)
            except Exception as e:
                logger.warning(f"Failed to fetch extraction data for recent uploads: {e}")
        
        # Claims table headers for nested claims_data
        claims_table_headers = [
            # {"field": "fileName", "label": "File"},
            {"field": "claim_number", "label": "Claim Number"},
            {"field": "payer", "label": "Payer"},
            {"field": "status", "label": "Status"},
            {"field": "uploaded", "label": "Uploaded", "isDate": True},
            {
                "label": "Actions",
                "actions": [
                    {"type": "view", "icon": "pi pi-eye", "roleAccess": ["admin", "reviewer", "viewer"]}
                   
                ],
            },
        ]
        
        table_rows = []
        for row in pg_recent:
            file_id = str(row[0])
            claims_table_data = []
            
            # Build claims data from extraction results
            extractions = extraction_data_map.get(file_id, [])
            for ext in extractions:
                claims_table_data.append({
                    "file_id": file_id,
                    "claim_id": ext.get("_id"),    
                    # "fileName": row[1],
                    "claim_number": ext.get("claimNumber", "-"),
                    "payer": ext.get("payerName", row[4] or "-"),
                    "status": ext.get("status", row[3]),
                    "uploaded": str(row[2]),
                    "isReviewed": ext.get("status") in ["approved", "rejected", "exception"]
                })
            
            # Calculate average aiConfidence for this file
            file_accuracy = 0.0
            if extractions:
                confidence_values = [ext.get("aiConfidence", 0) or 0 for ext in extractions]
                if confidence_values:
                    file_accuracy = round(sum(confidence_values) / len(confidence_values), 1)
            
            table_rows.append({
                "file_id": file_id,
                "fileName": row[1],
                "payer": row[4] or "-",
                "accuracy": f"{file_accuracy}%",
                "status": row[3],
                "reviewer": row[7] or "Unassigned",
                "uploaded": str(row[2]),
                "is_processing": row[3] == "ai_processing" if True else False,
                "claims_data": {
                    "tableHeaders": claims_table_headers,
                    "tableData": claims_table_data,
                } if claims_table_data else None,
            })
        # MongoDB recent uploads removed - using PostgreSQL data only
        resp_data = {
            "success": "Data retrieved successfully.",
            "widgets": {
                "uploaded": uploaded + pg_uploaded,
                # "processed": count_processed,
                "pendingReview": pending_review + pg_pending_review,
                "accuracyPercent": mongo_accuracy_percent,
                # "exceptions": exceptions + pg_exceptions,
                "exceptions": pg_exceptions,
                # "needsTemplate": pg_needs_template,
            },
            "recentUploadsData": {
                "tableHeaders": [
                    {"field": "fileName", "label": "File"},
                    {"field": "payer", "label": "Payer"},
                    {"field": "accuracy", "label": "Accuracy"},
                    {"field": "status", "label": "Status"},
                    {"field": "uploaded", "label": "Uploaded", "isDate": True},
                   
                ],
                "tableData": table_rows,
                "pagination": {
                    "total": len(table_rows),
                    "page": 1,
                    "page_size": 10,
                },
                "total_records": len(table_rows),
            }
        }
        cur.close()
        conn.close()
        return JSONResponse(content=resp_data, status_code=200)
    except Exception as e:
        logger.error("dashboard summary failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong while fetching dashboard data")

