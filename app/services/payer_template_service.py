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

def store_claims_in_postgres(file_id: str, flat_claims: List[Dict[str, Any]], org_id: str, payer_id: str, payer_name: str) -> List[str]:
    """
    Store EACH claim as a SEPARATE record in PostgreSQL claims table.
    Each claim from the same payer gets its own database entry.
    Returns list of claim IDs.
    """
    if not flat_claims:
        logger.info("No claims to store")
        return []
        
    conn = get_pg_conn()
    cur = conn.cursor()
    claim_ids = []
    
    try:
        logger.info(f"📋 Storing {len(flat_claims)} claims as SEPARATE records...")
        
        # Process EACH claim individually - no grouping by payer
        # for i, claim in enumerate(flat_claims, 1):

        print()
        print("flat_claims", flat_claims)
        print()
        # for i, claim in enumerate(flat_claims):
        # for i, claim in enumerate(flat_claims):
            # logger.info(f"Processing claim {i}/{len(flat_claims)}: {claim.get('claim_number', 'N/A')}")
            
            # Get or create payer for this claim
            # print("i:", i)
            # print("claim:", claim)
            # payer_name = claim.get('payer_name', 'Unknown')
            # payer_id = get_or_create_payer(payer_name, org_id)

        payer_name = payer_name
        payer_id = "b29354dc-5796-41dd-bcd1-244b0ea184f2"
        print("payer_id=====", payer_id)
            
        # Create SEPARATE payment record for EACH claim
        payment_id = str(uuid.uuid4())
        payment_ref = flat_claims["payment_reference"]
        claim_amount = flat_claims["claim_payment"]
            
        cur.execute("""
            INSERT INTO payments (
                id, org_id, file_id, payer_id, payment_reference,
                payment_date, payment_amount, currency, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, NOW(), NOW())
        """, (
            payment_id, org_id, file_id, payer_id, payment_ref,
            claim_amount, 'USD', 'extracted'
        ))
        
        # Create SEPARATE claim record
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

            flat_claims["claim_number"],
            flat_claims["patient_name"],
            flat_claims["patient_id"],
            payer_name,
            flat_claims["payment"],
            flat_claims["claim_payment"],
            flat_claims["total_paid"],
            flat_claims["adj_amount"], 
            flat_claims["claim_status_code"],
            flat_claims["dates_of_service"],
            flat_claims["dates_of_service"],
            90,  # Store AI confidence as validation_score
            'extracted'

        ))
        
        # Store service lines for this claim
        # service_lines = claim.get('service_lines', [])
        # for j, line in enumerate(service_lines, 1):
        service_line_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO service_lines (
                id, claim_id, line_number, cpt_code,
                dos_from, dos_to, billed_amount, allowed_amount, paid_amount,
                units, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            # service_line_id, claim_id, j,
            service_line_id, claim_id,
            1,
            flat_claims["procedure_code"],
            flat_claims["dates_of_service"],
            flat_claims["dates_of_service"],
            flat_claims["payment"],
            flat_claims["claim_payment"],
            flat_claims["payment"],
            flat_claims["units"]
        ))
        
        claim_ids.append(claim_id)
        # logger.info(f"✅ Stored claim '{claim.get('claim_number')}' as separate record (ID: {claim_id})")
    




        conn.commit()
        logger.info(f"✅ Successfully stored {len(claim_ids)} SEPARATE claims in PostgreSQL")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error storing claims: {e}")
        raise
    finally:
        cur.close()
        conn.close()
    
    return claim_ids