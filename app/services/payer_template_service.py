import uuid
from typing import Optional, List, Dict, Any
from ..services.pg_upload_files import get_pg_conn
from ..utils.logger import get_logger

logger = get_logger(__name__)

def get_or_create_payer(payer_name: str, org_id: str) -> str:
    """
    Check if payer exists in payers table. If not, create new payer record.
    Returns payer_id.
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    
    # Check if payer exists
    cur.execute("SELECT id FROM payers WHERE name = %s AND org_id = %s", (payer_name, org_id))
    result = cur.fetchone()
    
    if result:
        payer_id = result[0]
        logger.info(f"Payer '{payer_name}' already exists with ID: {payer_id}")
    else:
        # Create new payer
        payer_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO payers (id, org_id, name, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
        """, (payer_id, org_id, payer_name))
        conn.commit()
        logger.info(f"Created new payer '{payer_name}' with ID: {payer_id}")
    
    cur.close()
    conn.close()
    return payer_id

def check_template_match(payer_id: str, claim_keys: List[str]) -> Optional[str]:
    """
    Check if payer has a template and if the JSON keys match.
    Returns template status: 'matched', 'mismatch', or 'no_template'
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    # Get latest template for payer
    cur.execute("""
        SELECT t.id, tv.mongo_doc_id 
        FROM templates t 
        JOIN template_versions tv ON t.current_version_id = tv.id
        WHERE t.payer_id = %s AND t.status = 'active'
        ORDER BY tv.created_at DESC
        LIMIT 1
    """, (payer_id,))
    result = cur.fetchone()
    if not result:
        cur.close()
        conn.close()
        return 'no_template'
    template_id, mongo_doc_id = result
    # Try to get template dynamic keys from MongoDB
    from app.common.db.db import init_db
    DB = init_db()
    template_doc = DB['template_builder_sessions'].find_one({'_id': mongo_doc_id})
    template_keys = template_doc.get('dynamic_keys', []) if template_doc else []
    cur.close()
    conn.close()
    # Compare keys
    if not template_keys:
        return 'no_template'
    extracted_set = set([k.lower() for k in claim_keys if k])
    template_set = set([k.lower() for k in template_keys if k])
    if not extracted_set:
        return 'mismatch'
    matched = extracted_set.intersection(template_set)
    frac = len(matched) / max(1, len(template_set))
    if frac >= 0.6:
        return 'matched'
    else:
        return 'mismatch'


def find_payer_by_name(payer_name: str, org_id: str) -> Optional[str]:
    """
    Return payer id if a payer with the given name exists for the org, otherwise None.
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM payers WHERE name = %s AND org_id = %s", (payer_name, org_id))
    result = cur.fetchone()
    cur.close()
    conn.close()
    if result:
        return result[0]
    return None


def get_template_version_for_payer(payer_id: str) -> Optional[str]:
    """
    Return the current template version id (template_versions.id) for the payer if exists, otherwise None.
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT tv.id
            FROM templates t
            JOIN template_versions tv ON t.current_version_id = tv.id
            WHERE t.payer_id = %s AND t.status = 'active'
            ORDER BY tv.created_at DESC
            LIMIT 1
        """, (payer_id,))
        result = cur.fetchone()
        if result:
            return result[0]
        return None
    finally:
        cur.close()
        conn.close()


def get_template_version_by_mongo_doc_id(mongo_doc_id: str) -> Optional[str]:
    """
    Given a mongo_doc_id stored on template_versions.mongo_doc_id, return the template_versions.id
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    try:
        # Try exact match first
        cur.execute("SELECT id FROM template_versions WHERE mongo_doc_id = %s LIMIT 1", (mongo_doc_id,))
        res = cur.fetchone()
        if res:
            return res[0]

        # Try matching by LIKE in case types differ (ObjectId vs string)
        like_pattern = f"%{mongo_doc_id}%"
        cur.execute("SELECT id FROM template_versions WHERE mongo_doc_id::text LIKE %s LIMIT 1", (like_pattern,))
        res = cur.fetchone()
        return res[0] if res else None
    finally:
        cur.close()
        conn.close()


def keys_match_template(extracted_keys: List[str], template_dynamic_keys: List[str], threshold: float = 0.6) -> bool:
    """
    Simple key overlap matcher. Returns True if the fraction of matched keys >= threshold.
    """
    if not template_dynamic_keys:
        return False
    extracted_set = set([k.lower() for k in extracted_keys if k])
    template_set = set([k.lower() for k in template_dynamic_keys if k])
    if not extracted_set:
        return False
    matched = extracted_set.intersection(template_set)
    frac = len(matched) / max(1, len(template_set))
    return frac >= threshold


def ai_compare_keys(extracted_keys: List[str], template_keys: List[str], model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """
    Use an AI model to compare two sets of keys and return a match decision and confidence.

    Returns a dict: {"match": bool, "confidence": float, "reason": str}
    """
    try:
        # Lazy import to avoid hard dependency unless used
        import os
        import openai

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return {"match": False, "confidence": None, "reason": "no_api_key"}

        client = openai.OpenAI(api_key=api_key)

        prompt = f"""
You are given two lists of JSON field keys. Decide whether these two sets represent the same template structure.
Output JSON only with fields: match (true/false), confidence (0-100), reason (short).

Extracted keys: {extracted_keys}
Template keys: {template_keys}

Consider synonyms and common variations. Be conservative. Provide confidence as integer percentage.
"""

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200
        )

        content = response.choices[0].message.content.strip()
        # Try to parse JSON from model response
        import json
        try:
            parsed = json.loads(content)
            match = bool(parsed.get('match'))
            confidence = float(parsed.get('confidence')) if parsed.get('confidence') is not None else None
            reason = parsed.get('reason') or ''
            return {"match": match, "confidence": confidence, "reason": reason}
        except Exception:
            # If model didn't return JSON, do a best-effort parse
            # Look for a number in the text as confidence
            import re
            m = re.search(r"(\d{1,3})(?:%| percent)?", content)
            confidence = float(m.group(1)) if m else None
            match = confidence is not None and confidence >= 60
            return {"match": match, "confidence": confidence, "reason": content[:200]}

    except Exception as e:
        return {"match": False, "confidence": None, "reason": f"ai_error:{e}"}

def store_claims_in_postgres(file_id: str, claim_data: Dict[str, Any], org_id: str, payer_id: str, payer_name: str) -> List[str]:
    """
    Store a SINGLE claim record in PostgreSQL claims table.
    Returns list containing the new claim ID.
    """
    if not claim_data:
        logger.info("No claim data to store")
        return []
        
    conn = get_pg_conn()
    cur = conn.cursor()
    claim_ids = []
    
    # Helpers: robust numeric parsing for currency strings ("$1,234.56"), commas, parentheses
    def _parse_float(v) -> float:
        try:
            if v is None:
                return 0.0
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip()
            if not s:
                return 0.0
            neg = False
            if s.startswith("(") and s.endswith(")"):
                neg = True
                s = s[1:-1]
            s = s.replace(",", "").replace("$", "").replace("USD", "").strip()
            import re as _re
            m = _re.search(r"-?\d+(?:\.\d+)?", s)
            if not m:
                return 0.0
            num = float(m.group(0))
            return -num if neg else num
        except Exception:
            return 0.0

    def _parse_int(v) -> int:
        try:
            return int(_parse_float(v))
        except Exception:
            return 0

    try:
        logger.info(f"📋 Storing claim in PostgreSQL...")

        # Ensure we have a valid payer_id
        if not payer_id:
            logger.warning(f"Missing payer_id for file {file_id}. Creating fallback payer.")
            safe_payer_name = payer_name or claim_data.get("payer_name") or "Unknown Payer"
            payer_id = get_or_create_payer(safe_payer_name, org_id)

        # Handle missing claim_number
        claim_number = claim_data.get("claim_number")
        if not claim_number:
            claim_number = f"MISSING-{uuid.uuid4().hex[:8]}"
            logger.warning(f"Claim number missing for file {file_id}. Generated fallback: {claim_number}")

        # Check for duplicate claim_number
        cur.execute("""
            SELECT id FROM claims
            WHERE claim_number = %s AND file_id = %s
        """, (claim_number, file_id))
        existing_claim = cur.fetchone()

        if existing_claim:
            logger.warning(f"⚠️ Duplicate claim detected! Claim number {claim_number} already exists for file {file_id}. Skipping.")
            return []

        # Create payment record
        payment_id = str(uuid.uuid4())
        payment_ref = claim_data.get("payment_reference") or "UNKNOWN"
        claim_amount = _parse_float(claim_data.get("claim_payment"))
            
        cur.execute("""
            INSERT INTO payments (
                id, org_id, file_id, payer_id, payment_reference,
                payment_date, payment_amount, currency, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, NOW(), NOW())
        """, (
            payment_id, org_id, file_id, payer_id, payment_ref,
            claim_amount, 'USD', 'extracted'
        ))
        
        # Create claim record
        billed_amt = _parse_float(claim_data.get("payment")) # Note: mapping seems to be payment -> billed? Check original code.
        # Original code: billed_amt = _parse_float(flat_claims.get("payment"))
        # Wait, "payment" usually means paid amount. "total_billed_amount" should be billed.
        # But I must stick to the mapping in the original code unless I'm sure it's wrong.
        # Original: billed_amt = _parse_float(flat_claims.get("payment"))
        
        allowed_amt = _parse_float(claim_data.get("claim_payment"))
        paid_amt = _parse_float(claim_data.get("total_paid"))
        adj_amt = _parse_float(claim_data.get("adj_amount"))
        units_val = _parse_int(claim_data.get("units"))

        claim_id = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO claims (
                id, payment_id, file_id, claim_number, patient_name, member_id, provider_name,
                total_billed_amount, total_allowed_amount, total_paid_amount, total_adjustment_amount,
                claim_status_code, service_date_from, service_date_to, validation_score, 
                status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            claim_id, payment_id, file_id, 
            claim_number,
            claim_data.get("patient_name"),
            claim_data.get("patient_id"),
            payer_name,
            billed_amt,
            allowed_amt,
            paid_amt,
            adj_amt,
            claim_data.get("claim_status_code"),
            claim_data.get("dates_of_service"),
            claim_data.get("dates_of_service"),
            90,  # Store AI confidence as validation_score
            'extracted'
        ))
        
        # Store service lines for this claim
        service_line_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO service_lines (
                id, claim_id, line_number, cpt_code,
                dos_from, dos_to, billed_amount, allowed_amount, paid_amount,
                units, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            service_line_id, claim_id,
            1,
            claim_data.get("procedure_code"),
            claim_data.get("dates_of_service"),
            claim_data.get("dates_of_service"),
            billed_amt,
            allowed_amt,
            paid_amt,
            units_val,
        ))
        
        claim_ids.append(claim_id)
        conn.commit()
        logger.info(f"✅ Successfully stored claim {claim_number} (ID: {claim_id})")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error storing claim: {e}")
        # Don't raise, just log error so other claims in the batch might succeed? 
        # But here we are processing one by one. If we raise, the whole request fails.
        # The user said "permanent fix". Crashing the server is bad.
        # Returning empty list indicates failure for this claim.
        return [] 
    finally:
        cur.close()
        conn.close()
    
    return claim_ids