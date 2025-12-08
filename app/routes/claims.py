from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import psycopg2
from ..services.pg_upload_files import get_pg_conn
import json

router = APIRouter(prefix="/claims", tags=["claims"])

@router.get("/latest/{count}")
def get_latest_claims(count: int = 10) -> List[Dict[str, Any]]:
    """
    Get the latest claims from PostgreSQL database.
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        # Query to get latest claims with payer and payment info
        query = """
        SELECT 
            c.id as claim_id,
            c.claim_number,
            c.patient_name,
            c.member_id,
            c.provider_name,
            c.total_billed_amount,
            c.total_allowed_amount,
            c.total_paid_amount,
            c.total_adjustment_amount,
            c.service_date_from,
            c.service_date_to,
            c.validation_score,
            c.status,
            c.created_at,
            p.name as payer_name,
            py.payment_reference,
            py.payment_amount,
            py.payment_date
        FROM claims c
        JOIN payments py ON c.payment_id = py.id
        JOIN payers p ON py.payer_id = p.id
        ORDER BY c.created_at DESC
        LIMIT %s
        """
        
        cur.execute(query, (count,))
        rows = cur.fetchall()
        
        # Convert to list of dictionaries
        columns = [desc[0] for desc in cur.description]
        claims = []
        
        for row in rows:
            claim_dict = dict(zip(columns, row))
            # Convert Decimal and datetime to string for JSON serialization
            for key, value in claim_dict.items():
                if hasattr(value, 'isoformat'):  # datetime
                    claim_dict[key] = value.isoformat()
                elif str(type(value)) == "<class 'decimal.Decimal'>":  # Decimal
                    claim_dict[key] = float(value)
            claims.append(claim_dict)
        
        return claims
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

@router.get("/by-file/{file_id}")
def get_claims_by_file(file_id: str) -> List[Dict[str, Any]]:
    """
    Get all claims for a specific file ID.
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        query = """
        SELECT 
            c.id as claim_id,
            c.claim_number,
            c.patient_name,
            c.member_id,
            c.provider_name,
            c.total_billed_amount,
            c.total_allowed_amount,
            c.total_paid_amount,
            c.total_adjustment_amount,
            c.service_date_from,
            c.service_date_to,
            c.validation_score,
            c.status,
            c.created_at,
            p.name as payer_name,
            py.payment_reference,
            py.payment_amount
        FROM claims c
        JOIN payments py ON c.payment_id = py.id
        JOIN payers p ON py.payer_id = p.id
        WHERE c.file_id = %s
        ORDER BY c.created_at ASC
        """
        
        cur.execute(query, (file_id,))
        rows = cur.fetchall()
        
        if not rows:
            raise HTTPException(status_code=404, detail=f"No claims found for file ID: {file_id}")
        
        # Convert to list of dictionaries
        columns = [desc[0] for desc in cur.description]
        claims = []
        
        for row in rows:
            claim_dict = dict(zip(columns, row))
            # Convert types for JSON serialization
            for key, value in claim_dict.items():
                if hasattr(value, 'isoformat'):  # datetime
                    claim_dict[key] = value.isoformat()
                elif str(type(value)) == "<class 'decimal.Decimal'>":  # Decimal
                    claim_dict[key] = float(value)
            claims.append(claim_dict)
        
        return claims
        
    except Exception as e:
        if "No claims found" in str(e):
            raise e
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

@router.get("/stats")
def get_claims_stats() -> Dict[str, Any]:
    """
    Get statistics about stored claims.
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        # Get basic stats
        queries = {
            "total_claims": "SELECT COUNT(*) FROM claims",
            "total_payments": "SELECT COUNT(*) FROM payments", 
            "total_payers": "SELECT COUNT(*) FROM payers",
            "total_amount_paid": "SELECT COALESCE(SUM(total_paid_amount), 0) FROM claims",
            "total_amount_billed": "SELECT COALESCE(SUM(total_billed_amount), 0) FROM claims"
        }
        
        stats = {}
        for key, query in queries.items():
            cur.execute(query)
            stats[key] = cur.fetchone()[0]
        
        # Get payer breakdown
        cur.execute("""
            SELECT p.name, COUNT(c.id) as claim_count, 
                   COALESCE(SUM(c.total_paid_amount), 0) as total_paid
            FROM payers p 
            LEFT JOIN payments py ON p.id = py.payer_id
            LEFT JOIN claims c ON py.id = c.payment_id 
            GROUP BY p.name 
            ORDER BY claim_count DESC
        """)
        
        payer_stats = []
        for row in cur.fetchall():
            payer_stats.append({
                "payer_name": row[0],
                "claim_count": row[1],
                "total_paid": float(row[2])
            })
        
        stats["payer_breakdown"] = payer_stats
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()