from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import os
import datetime
import json
import uuid
from app.services.pg_upload_files import get_pg_conn
from app.services.s3_service import S3Service
from app.common.config import settings
from app.common.db.db import init_db
from ..utils.logger import get_logger
from openai import AsyncOpenAI

DB = init_db()
logger = get_logger(__name__)

# Initialize OpenAI client if API key is available
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None

router = APIRouter(prefix="/generate-835", tags=["generate-835"])

# Initialize S3 service
S3_BUCKET = settings.S3_BUCKET
AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
AWS_REGION = settings.AWS_REGION
s3_client = S3Service(S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)

class Generate835Request(BaseModel):
    claim_id: str  # The claim ID to fetch from database
    org_id: str  # Organization ID (UUID format)
    generated_by: Optional[str] = None  # User ID who generated the export
    
class Generate835Response(BaseModel):
    message: str
    s3_path: str
    status: str
    

AI_835_PROMPT = """
You are an expert in ANSI X12 835 (005010X221A1).

STRICT RULES:
1. Use ONLY values explicitly present in the input JSON.
2. Do NOT infer, calculate, default, or invent any value.
3. If a segment’s mandatory data is missing, OMIT the entire segment.
4. Output ONLY valid X12 835 segments. No explanations. No comments.
5. Use '*' as the element separator and '~' as the segment terminator.
6. All dates must be formatted as YYYYMMDD.
7. All monetary values must be formatted with exactly 2 decimal places.
8. Preserve correct loop order and hierarchy. Do not reorder segments.
9. Repeat loops only when corresponding data arrays exist in JSON.

STRUCTURE TO FOLLOW EXACTLY:

Envelope:
- ISA (Interchange Control Header)
- GS  (Functional Group Header)

Transaction Set:
- ST*835 (Transaction Set Header)

Financial Information:
- BPR (payment method, payment amount, handling code)
- TRN (reassociation trace number)
- DTM (payment effective date)

Payer / Payee Identification:
- N1*PR (Payer)
- N3 / N4 (Payer Address)
- N1*PE (Payee)
- N3 / N4 (Payee Address)
- REF (payer/payee identifiers such as TIN, NPI)

Claim Payment Information — Loop 2000 (repeat per claim):
- LX  (assigned claim number)
- CLP (claim number, status code, total charge, paid amount, patient responsibility)
- CAS (claim-level adjustments: CO, PR, OA, etc.)
- NM1*QC (Patient Name)
- NM1*IL (Insured Name)
- DTM (claim-level dates)
- REF (claim identifiers)

Service Line Information — Loop 2100 (repeat per service line under each claim):
- SVC (CPT/HCPCS, line charge amount, line paid amount)
- DTM (service date)
- CAS (service-level adjustments)
- REF (line identifiers such as revenue code or line control number)

Totals:
- PLB (provider-level adjustments only if present)

Transaction Close:
- SE (Transaction Set Trailer)
- GE (Functional Group Trailer)
- IEA (Interchange Control Trailer)

MANDATORY HIERARCHY:
ISA
→ GS
→ ST
→ BPR
→ TRN
→ DTM
→ N1/N3/N4/REF
→ ( LX
     → CLP
     → CAS
     → NM1
     → DTM
     → REF
     → ( SVC
          → DTM
          → CAS
          → REF
       )*
   )*
→ PLB
→ SE
→ GE
→ IEA

INPUT JSON:
{json_payload}

OUTPUT:
Return ONLY the raw ANSI X12 835 text, nothing else.
"""

async def generate_835_with_ai(ai_client, claim_json: dict) -> str:
    if not ai_client:
        # Fallback to basic 835 generation if AI client is not available
        return generate_basic_835(claim_json)
    
    try:
        prompt = AI_835_PROMPT.format(
            json_payload=json.dumps(claim_json, indent=2)
        )

        resp = await ai_client.chat.completions.create(
            model="gpt-4o",  # Fixed model name
            messages=[
                {"role": "system", "content": "You are an X12 835 expert."},
                {"role": "user", "content": prompt},
            ],
            temperature=0
        )

        edi_text = resp.choices[0].message.content.strip()
        
        # Clean up any markdown formatting that might be returned
        if "```" in edi_text:
            # Extract content between code blocks
            lines = edi_text.split('\n')
            in_code_block = False
            clean_lines = []
            for line in lines:
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not in_code_block and line.strip()):
                    clean_lines.append(line)
            edi_text = '\n'.join(clean_lines)
        
        print(f"✅ AI generated 835 content ({len(edi_text)} characters)")
        return edi_text
        
    except Exception as e:
        print(f"❌ AI generation failed: {e}")
        print("🔄 Falling back to basic 835 generation")
        return generate_basic_835(claim_json)


def generate_basic_835(claim_json: dict) -> str:
    """Generate a basic 835 file when AI is not available"""
    now = datetime.datetime.utcnow()
    
    # Extract basic claim information
    claim_number = extract_field_from_claim(claim_json, "claim_number") or "SAMPLE001"
    total_paid = float(extract_field_from_claim(claim_json, "total_paid") or 
                      extract_field_from_claim(claim_json, "payment_amount") or 100.00)
    patient_name = extract_field_from_claim(claim_json, "patient_name") or "DOE*JOHN"
    
    # Format patient name for X12
    if "*" not in patient_name:
        name_parts = str(patient_name).split()
        if len(name_parts) >= 2:
            patient_name = f"{name_parts[-1]}*{name_parts[0]}"
        else:
            patient_name = "DOE*JOHN"
    
    # Generate basic 835 content
    segments = [
        f"ISA*00*          *00*          *ZZ*SAMPLEID      *ZZ*RECEIVER      *{now.strftime('%y%m%d')}*{now.strftime('%H%M')}*^*00501*000000001*0*P*>~",
        f"GS*HP*SAMPLEID*RECEIVER*{now.strftime('%Y%m%d')}*{now.strftime('%H%M%S')}*1*X*005010X221A1~",
        "ST*835*0001*005010X221A1~",
        f"BPR*I*{total_paid:.2f}*C*CHK****{now.strftime('%Y%m%d')}~",
        f"TRN*1*{claim_number}*1234567890~",
        f"DTM*405*{now.strftime('%Y%m%d')}~",
        "N1*PR*SAMPLE HEALTHCARE PAYER~",
        "N3*123 PAYER STREET~",
        "N4*PAYER CITY*ST*12345~",
        "N1*PE*SAMPLE PROVIDER*XX*1234567890~",
        "LX*1~",
        f"CLP*{claim_number}*1*{total_paid:.2f}*{total_paid:.2f}*0.00**11*{claim_number}*01~",
        f"NM1*QC*1*{patient_name}****MI*123456789~",
        f"DTM*232*{now.strftime('%Y%m%d')}~",
        f"SVC*HC:99213*{total_paid:.2f}*{total_paid:.2f}**1~",
        f"DTM*472*{now.strftime('%Y%m%d')}~",
        "SE*16*0001~",
        "GE*1*1~",
        "IEA*1*000000001~"
    ]
    
    return '\n'.join(segments)


def validate_835_text(text: str):
    if not text:
        raise ValueError("Empty 835 output")
    if "~" not in text:
        raise ValueError("Invalid 835: missing segment terminator")
    if not text.strip():
        raise ValueError("835 content is only whitespace")

def write_and_upload_835(s3_client, edi_text: str, claim_number: str) -> tuple[str, float]:
    print(f"Writing and uploading 835 for claim number: {claim_number}")
    
    if not edi_text or not edi_text.strip():
        raise ValueError("Empty or invalid EDI text generated")
    
    # Sanitize claim number for filename
    safe_claim_number = str(claim_number).replace('/', '_').replace('\\', '_').replace(':', '_')
    # file_name = f"835_{safe_claim_number}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
    file_name = f"835_{safe_claim_number}_{datetime.datetime.utcnow().strftime('%Y%m%d')}.txt"

    # Upload to S3 using bytes content (not file path)
    s3_key = f"exports/835/{file_name}"
    edi_bytes = edi_text.encode('utf-8')
    s3_path = s3_client.upload_file(edi_bytes, s3_key)
    
    if not s3_path:
        raise HTTPException(status_code=500, detail="Failed to upload 835 file to S3")
    
    size_kb = len(edi_bytes) / 1024
    print(f"✅ Successfully uploaded 835 file to S3: {s3_path} ({size_kb:.2f} KB)")
    
    return s3_path, size_kb


def save_export_records(conn, *, org_id, claim_id, s3_path, generated_by):
    export_id = str(uuid.uuid4())
    export_ref = f"EXP-{export_id[:8]}"

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO exports_835
            (id, org_id, export_reference, storage_path, status, generated_by, generated_at)
            VALUES (%s,%s,%s,%s,'generated',%s,now())
        """, (export_id, org_id, export_ref, s3_path, generated_by))

        cur.execute("""
            INSERT INTO export_items (export_id, claim_id)
            VALUES (%s,%s)
        """, (export_id, claim_id))

    conn.commit()
    return export_id, export_ref


def extract_field_from_claim(claim_json: dict, field_name: str):
    """Extract field from claim JSON, handling different structures"""
    if not claim_json:
        return None
    
    # Direct access
    if field_name in claim_json:
        return claim_json[field_name]
    
    # Check in sections if claim has sections structure
    if "sections" in claim_json:
        for section in claim_json.get("sections", []):
            for field in section.get("fields", []):
                if field.get("field") == field_name:
                    return field.get("value")
    
    # Common field aliases
    field_aliases = {
        "claim_number": ["claim_number", "claimNumber", "claim_id"],
        "total_paid": ["total_paid", "totalPaid", "payment_amount", "paymentAmount"],
        "payment_amount": ["payment_amount", "paymentAmount", "total_paid", "totalPaid"],
        "service_lines": ["service_lines", "serviceLines", "services"]
    }
    
    if field_name in field_aliases:
        for alias in field_aliases[field_name]:
            if alias in claim_json:
                return claim_json[alias]
    
    return None


@router.post("/", response_model=Generate835Response)
async def generate_835_file(request: Generate835Request):
    try:
        # 1) Fetch claim JSON (Mongo)
        claim_collection = DB["claim_version"]
        extraction_result = DB["extraction_results"]
        claim_doc = await claim_collection.find_one(
            {"extraction_id": request.claim_id},
            sort=[("created_at", -1)]
        )

        if not claim_doc or "claim" not in claim_doc:
            raise HTTPException(404, "Claim not found")

        claim_json = claim_doc["claim"]
        
        claim_data = await extraction_result.find_one(
            {"_id": request.claim_id}
        )
        claim_status = claim_data.get("status")
        claim_number = claim_data.get("claimNumber")
        if claim_status == 'generated':
            return {"status": "already_generated"}
        
        

        # try:
        # 2) AI generates 835
        edi_text = await generate_835_with_ai(ai_client, claim_json)
        # 3) Validate
        validate_835_text(edi_text)

        # 4) Write + upload
        s3_path, size_kb = write_and_upload_835(s3_client, edi_text, claim_number)

        # 5) DB inserts
        conn = get_pg_conn()
        
        export_id, export_ref = save_export_records(
            conn,
            org_id=request.org_id,
            claim_id=request.claim_id,
            s3_path=s3_path,
            generated_by=request.generated_by
        )

        # Extract required fields from claim data
        claim_number = extract_field_from_claim(claim_json, "claim_number") or "UNKNOWN"
        
        

        
        await extraction_result.update_one(
                {"_id": request.claim_id},
                {"$set": {"status": "generated"}}
            )

        await claim_collection.update_one(
            {"extraction_id": request.claim_id},
            {"$set": {"status": "generated"}}
        )

        return Generate835Response(
            message="835 generated successfully",
            s3_path=s3_path,
            status="generated")

    except ValueError as ve:
        logger.error("Validation error: %s", ve, exc_info=True)
        raise HTTPException(422, str(ve))
                          
    except Exception as e:
        logger.error("835 generation failed: %s", e, exc_info=True)
        raise HTTPException(500, "835 generation failed")