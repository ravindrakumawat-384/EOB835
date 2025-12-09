from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import os
import datetime
import json

from app.services.payer_template_service import get_or_create_payer, store_claims_in_postgres
from app.services.mongo_extraction import store_extraction_result
from app.services.pg_upload_files import get_pg_conn
from app.services.s3_service import S3Service
from app.services.ai_835_generator import ai_835_generator
from app.common.config import settings
import app.common.db.db as db_module

router = APIRouter(prefix="/generate-835", tags=["generate-835"])

# Initialize S3 service
S3_BUCKET = settings.S3_BUCKET
AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
AWS_REGION = settings.AWS_REGION
s3_client = S3Service(S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)

class Generate835Request(BaseModel):
    claim_id: str  # The claim ID to fetch from database
    org_id: str = "00000000-0000-0000-0000-000000000000"  # Organization ID (UUID format)
    generated_by: Optional[str] = None  # User ID who generated the export
    use_ai: bool = True  # Enable AI-powered 835 generation (default: True)
    
class Generate835Response(BaseModel):
    success: bool
    export_id: str  # UUID of the export record
    export_reference: str
    file_name: str
    s3_path: str
    file_size_kb: float
    claim_number: str
    total_amount: float
    service_lines_count: int
    generated_at: str
    status: str
    message: str

def get_claim_json_from_database(claim_id: str) -> Dict[str, Any]:
    """
    Fetch claim data from PostgreSQL and MongoDB and return as JSON
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        # Get claim data with related tables
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
            c.file_id,
            p.name as payer_name,
            py.payment_reference,
            py.payment_amount,
            py.payment_date
        FROM claims c
        JOIN payments py ON c.payment_id = py.id
        JOIN payers p ON py.payer_id = p.id
        WHERE c.id = %s
        """
        
        cur.execute(query, (claim_id,))
        row = cur.fetchone()
        
        if not row:
            # Try to get basic claim data without joins
            print(f"⚠️ No data found with joins, trying simplified query...")
            cur.execute("SELECT * FROM claims WHERE id = %s", (claim_id,))
            basic_row = cur.fetchone()
            
            if not basic_row:
                raise HTTPException(status_code=404, detail=f"Claim ID {claim_id} not found")
            
            # Convert basic claim data
            basic_columns = [desc[0] for desc in cur.description]
            claim_data = dict(zip(basic_columns, basic_row))
            
            # Set default values for missing joined data
            claim_data.update({
                'payer_name': 'HEALTHCARE PAYER',
                'payment_reference': f"PAY-{claim_data.get('claim_number', 'UNK')}",
                'payment_amount': claim_data.get('total_paid_amount', 0),
                'payment_date': claim_data.get('created_at')
            })
            
            print(f"✅ Using basic claim data with defaults")
        else:
            # Convert full joined data to dictionary
            columns = [desc[0] for desc in cur.description]
            claim_data = dict(zip(columns, row))
        
        # Debug: Print claim data
        print(f"🔍 DEBUG - Claim Data Retrieved:")
        for key, value in claim_data.items():
            print(f"   {key}: {value}")
        
        # Get service lines (handle if table doesn't exist)
        service_lines = []
        try:
            cur.execute("""
                SELECT line_number, cpt_code, dos_from, dos_to, 
                       billed_amount, allowed_amount, paid_amount, units
                FROM service_lines 
                WHERE claim_id = %s 
                ORDER BY line_number
            """, (claim_id,))
            
            for sl_row in cur.fetchall():
                sl_columns = [desc[0] for desc in cur.description]
                service_line = dict(zip(sl_columns, sl_row))
                service_lines.append(service_line)
        except Exception as e:
            print(f"⚠️ Service lines table not found or empty: {e}")
            # Create default service line from claim data
            service_lines = [{
                "line_number": 1,
                "cpt_code": "99213",  # Default CPT code
                "dos_from": claim_data.get('service_date_from'),
                "dos_to": claim_data.get('service_date_to'),
                "billed_amount": claim_data.get('total_billed_amount', 0),
                "allowed_amount": claim_data.get('total_allowed_amount', 0),
                "paid_amount": claim_data.get('total_paid_amount', 0),
                "units": 1
            }]
        
        claim_data["service_lines"] = service_lines
        
        # Convert datetime/decimal to string for JSON serialization
        for key, value in claim_data.items():
            if hasattr(value, 'isoformat'):  # datetime
                claim_data[key] = value.isoformat()
            elif str(type(value)) == "<class 'decimal.Decimal'>":  # Decimal
                claim_data[key] = float(value)
        
        return claim_data
        
    finally:
        cur.close()
        conn.close()

def convert_json_to_835_format(claim_json: Dict[str, Any], use_ai: bool = True) -> str:
    """
    Convert claim JSON data to proper EDI 835 format using AI-powered or standard generation
    """
    if use_ai:
        print(f"🤖 Starting AI-powered 835 generation...")
        
        # Try AI-powered generation
        try:
            ai_generated_835 = ai_835_generator.generate_intelligent_835(claim_json)
            if ai_generated_835 and len(ai_generated_835.strip()) > 100:
                print(f"✅ AI generated 835 format successfully ({len(ai_generated_835)} chars)")
                return ai_generated_835
            else:
                print(f"⚠️  AI generation returned insufficient content, using fallback")
        except Exception as e:
            print(f"❌ AI generation failed: {e}")
            print(f"🔄 Falling back to standard generation")
    else:
        print(f"📝 AI disabled, using standard generation...")
    
    # Standard generation (fallback or when AI is disabled)
    print(f"📝 Using standard 835 generation...")
    now = datetime.datetime.utcnow()
    
    # Helper function to safely format amounts
    def format_amount(value):
        try:
            return f"{float(value or 0):.2f}"
        except (ValueError, TypeError):
            return "0.00"
    
    # Helper function to format dates
    def format_date(date_str):
        try:
            if date_str and '-' in str(date_str):
                return str(date_str).replace('-', '')
            return now.strftime('%Y%m%d')
        except:
            return now.strftime('%Y%m%d')
    
    # Extract and format data safely with better defaults
    total_paid = format_amount(claim_json.get('total_paid_amount') or claim_json.get('payment_amount', 0))
    total_billed = format_amount(claim_json.get('total_billed_amount', 0))
    total_adjustment = format_amount(claim_json.get('total_adjustment_amount', 0))
    
    # Use payment_reference or generate one from claim
    payment_ref = str(claim_json.get('payment_reference') or f"PAY-{claim_json.get('claim_number', 'UNK')}")
    payment_ref = payment_ref.replace('*', '').replace('~', '')[:30]
    
    # Use actual payer name or default
    payer_name = str(claim_json.get('payer_name') or 'HEALTHCARE PAYER')
    payer_name = payer_name.replace('*', '').replace('~', '')[:35]
    
    # Use actual claim number
    claim_number = str(claim_json.get('claim_number') or 'CLM-UNKNOWN')
    claim_number = claim_number.replace('*', '').replace('~', '')[:20]
    
    # Patient name formatting for 835 - handle None/empty values
    patient_name_raw = claim_json.get('patient_name')
    if patient_name_raw and str(patient_name_raw).strip():
        patient_name = str(patient_name_raw).strip()
    else:
        patient_name = 'DOE, JOHN'  # Better default
    
    # Handle different name formats
    if ',' in patient_name:
        # "LAST, FIRST MIDDLE" format
        parts = patient_name.split(',')
        patient_last = parts[0].strip()
        remaining = parts[1].strip() if len(parts) > 1 else ''
        name_parts = remaining.split() if remaining else []
        patient_first = name_parts[0] if len(name_parts) > 0 else ''
        patient_middle = name_parts[1] if len(name_parts) > 1 else ''
    else:
        # "FIRST LAST" or "FIRST MIDDLE LAST" format
        name_parts = patient_name.split()
        patient_first = name_parts[0] if len(name_parts) > 0 else 'JOHN'
        patient_last = name_parts[-1] if len(name_parts) > 1 else 'DOE'
        patient_middle = name_parts[1] if len(name_parts) > 2 else ''
    
    # Member ID handling
    member_id_raw = claim_json.get('member_id')
    member_id = str(member_id_raw) if member_id_raw else claim_number
    member_id = member_id.replace('*', '').replace('~', '')[:30]
    service_date = format_date(claim_json.get('service_date_from'))
    current_date = now.strftime('%Y%m%d')
    current_time = now.strftime('%H%M')
    
    # Debug: Print formatted values
    print(f"🔍 DEBUG - Formatted 835 Data:")
    print(f"   Claim Number: {claim_number}")
    print(f"   Patient: {patient_last}, {patient_first} {patient_middle}")
    print(f"   Member ID: {member_id}")
    print(f"   Payer: {payer_name}")
    print(f"   Payment Ref: {payment_ref}")
    print(f"   Total Billed: ${total_billed}")
    print(f"   Total Paid: ${total_paid}")
    print(f"   Service Lines: {len(claim_json.get('service_lines', []))}")
    
    # Generate proper ISA header
    interchange_control = f"{now.strftime('%y%m%d%H%M%S')}"
    
    # Build proper EDI 835 segments
    segments = [
        # ISA - Interchange Control Header
        f"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *{now.strftime('%y%m%d')}*{current_time}*^*00501*{interchange_control[:9].ljust(9, '0')}*0*P*:~",
        
        # GS - Functional Group Header
        f"GS*HP*SENDER*RECEIVER*{current_date}*{current_time}*1*X*005010X221A1~",
        
        # ST - Transaction Set Header
        "ST*835*0001*005010X221A1~",
        
        # BPR - Beginning Segment for Payment Order/Remittance Advice
        f"BPR*I*{total_paid}*C*ACH*CCP*01*{payment_ref}*DA*123456789*1234567890*{current_date}*01*123456789*DA*123456789~",
        
        # TRN - Reassociation Trace Number
        f"TRN*1*{payment_ref}*1234567890~",
        
        # CUR - Currency (optional)
        "CUR*85*USD~",
        
        # REF - Reference Information (optional)
        f"REF*EV*{payment_ref}~",
        
        # DTM - Date/Time Reference
        f"DTM*405*{current_date}~",
        
        # N1 Loop - Payer Identification
        f"N1*PR*{payer_name}~",
        "N3*P.O. BOX 31362~",
        "N4*SALT LAKE CITY*UT*84131~",
        
        # N1 Loop - Payee Identification  
        "N1*PE*NEXGEN HEALTHCARE LLC*XX*1234567890~",
        "N3*21 WATERVILLE RD~",
        "N4*AVON*CT*06001~",
        
        # LX - Header Number
        "LX*1~",
        
        # CLP - Claim Payment Information
        f"CLP*{claim_number}*1*{total_billed}*{total_paid}*{total_adjustment}*MC*{payment_ref}*11*1~",
        
        # NM1 - Patient Name
        f"NM1*QC*1*{patient_last}*{patient_first}*{patient_middle}***MI*{member_id}~",
        
        # DTM - Statement Date
        f"DTM*232*{service_date}~"
    ]
    
    # Service lines - use AI enhancement for better accuracy (if enabled)
    service_lines = claim_json.get('service_lines', [])
    if not service_lines:
        if use_ai:
            print(f"🤖 No service lines found, using AI to generate appropriate ones...")
            try:
                # Use AI to generate intelligent service lines
                service_lines = ai_835_generator.enhance_service_lines_with_ai(claim_json)
                print(f"✅ AI generated {len(service_lines)} service lines")
            except Exception as e:
                print(f"❌ AI service line generation failed: {e}")
                service_lines = None  # Will use fallback below
        
        if not service_lines:  # Fallback for both AI failure and when AI is disabled
            print(f"📝 Using standard service line generation...")
            # Fallback to default service line
            default_billed = claim_json.get('total_billed_amount', 0)
            default_paid = claim_json.get('total_paid_amount') or claim_json.get('payment_amount', 0)
            
            service_lines = [{
                'cpt_code': '99213',  # Office visit code
                'description': 'Office Visit Level 3',
                'billed_amount': default_billed if default_billed and float(default_billed) > 0 else 150.00,
                'paid_amount': default_paid if default_paid and float(default_paid) > 0 else 120.00,
                'units': 1,
                'dos_from': claim_json.get('service_date_from')
            }]
    else:
        print(f"📋 Using existing {len(service_lines)} service lines from claim data")
    
    # Add service line segments
    for i, sl in enumerate(service_lines):
        cpt_code = str(sl.get('cpt_code', 'UNKNOWN')).replace('*', '').replace('~', '')
        billed_amt = format_amount(sl.get('billed_amount', 0))
        paid_amt = format_amount(sl.get('paid_amount', 0))
        units = str(sl.get('units', 1))
        dos_date = format_date(sl.get('dos_from'))
        
        # SVC - Service Payment Information
        segments.append(f"SVC*HC:{cpt_code}*{billed_amt}*{paid_amt}**{units}~")
        
        # DTM - Service Date
        segments.append(f"DTM*472*{dos_date}~")
        
        # CAS - Claim Adjustment (if needed)
        if float(billed_amt) != float(paid_amt):
            adjustment = format_amount(float(billed_amt) - float(paid_amt))
            segments.append(f"CAS*CO*45*{adjustment}~")
    
    # Transaction Set Trailer
    segment_count = len([s for s in segments if s.startswith(('ST', 'BPR', 'TRN', 'CUR', 'REF', 'DTM', 'N1', 'N3', 'N4', 'LX', 'CLP', 'NM1', 'SVC', 'CAS'))]) + 1
    segments.append(f"SE*{segment_count}*0001~")
    
    # GE - Functional Group Trailer
    segments.append("GE*1*1~")
    
    # IEA - Interchange Control Trailer
    segments.append(f"IEA*1*{interchange_control[:9].ljust(9, '0')}~")
    
    return "\n".join(segments)

@router.post("/", response_model=Generate835Response)
def generate_835_file(request: Generate835Request, background_tasks: BackgroundTasks):
    """
    Generate 835 file from claim ID:
    1. Fetch claim JSON data from database (PostgreSQL + MongoDB)
    2. Convert JSON to 835 format
    3. Save file and return download info
    """
    try:
        # 1. Fetch claim data from database as JSON
        print(f"🔍 Fetching claim data for ID: {request.claim_id}")
        claim_json = get_claim_json_from_database(request.claim_id)
        
        print(f"📋 Found claim: {claim_json.get('claim_number', 'UNKNOWN')}")
        print(f"💰 Total Amount: ${claim_json.get('total_paid_amount', 0)}")
        print(f"📊 Service Lines: {len(claim_json.get('service_lines', []))}")
        
        # 2. Convert JSON to 835 format
        ai_mode = "AI-powered" if request.use_ai else "standard"
        print(f"🔄 Converting JSON to 835 format using {ai_mode} generation...")
        file_835_content = convert_json_to_835_format(claim_json, use_ai=request.use_ai)
        
        # 3. Generate file with claim number-based naming
        now = datetime.datetime.utcnow()
        
        # Sanitize claim number for filename (remove invalid characters)
        claim_number = claim_json.get('claim_number', 'CLM-UNKNOWN')
        safe_claim_number = str(claim_number).replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        
        # Create descriptive filename with timestamp
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        file_name = f"{safe_claim_number}_835_{timestamp}.txt"
        file_path = f"/tmp/{file_name}"
        
        with open(file_path, "w") as f:
            f.write(file_835_content)
        
        print(f"✅ 835 file generated: {file_name}")
        
        # 4. Upload file to S3
        print(f"📤 Uploading 835 file to S3...")
        s3_file_key = f"exports/835/{now.strftime('%Y/%m/%d')}/{file_name}"
        s3_path = s3_client.upload_file(file_835_content.encode('utf-8'), s3_file_key)
        
        if not s3_path:
            raise HTTPException(status_code=500, detail="Failed to upload file to S3")
        
        print(f"✅ File uploaded to S3: {s3_path}")
        
        # 5. Store export data in database
        export_reference = f"EXP835-{safe_claim_number}-{timestamp}"
        print(f"💾 Storing export data in database...")
        
        export_id = store_835_export_in_database(
            claim_id=request.claim_id,
            claim_json=claim_json,
            export_reference=export_reference,
            s3_path=s3_path,
            org_id=request.org_id,
            generated_by=request.generated_by
        )
        
        # 6. Prepare response
        file_size_kb = round(len(file_835_content.encode('utf-8')) / 1024, 1)
        
        # Schedule local file cleanup
        background_tasks.add_task(cleanup_file, file_path, delay=300)  # 5 minutes
        
        return {
            "success": True,
            "export_id": export_id,
            "export_reference": export_reference,
            "file_name": file_name,
            "s3_path": s3_path,
            "file_size_kb": file_size_kb,
            "claim_number": claim_json.get('claim_number', 'UNKNOWN'),
            "total_amount": float(claim_json.get('total_paid_amount', 0)),
            "service_lines_count": len(claim_json.get('service_lines', [])),
            "generated_at": now.isoformat(),
            "status": "generated",
            "message": "835 file generated and uploaded to S3"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating 835 file: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating 835 file: {str(e)}")

def create_835_export_tables():
    """Create exports_835 and export_items tables if they don't exist"""
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        # Create exports_835 table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exports_835 (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                org_id UUID NOT NULL,
                export_reference TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending','generated','downloaded','failed')),
                generated_by UUID NULL,
                generated_at TIMESTAMPTZ NULL,
                error_message TEXT NULL
            )
        """)
        
        # Create export_items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS export_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                export_id UUID NOT NULL,
                payment_id UUID NULL,
                claim_id UUID NULL,
                FOREIGN KEY (export_id) REFERENCES exports_835(id)
            )
        """)
        
        # Create indexes for faster lookups
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_exports_835_org_id ON exports_835(org_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_exports_835_status ON exports_835(status)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_items_export_id ON export_items(export_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_items_claim_id ON export_items(claim_id)
        """)
        
        conn.commit()
        print("✅ exports_835 and export_items tables created/verified")
        
    except Exception as e:
        print(f"⚠️ Error creating export tables: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def store_835_export_in_database(claim_id: str, claim_json: Dict[str, Any], 
                               export_reference: str, s3_path: str, 
                               org_id: str = "00000000-0000-0000-0000-000000000000", generated_by: str = None) -> str:
    """Store 835 export data in PostgreSQL using new table structure"""
    
    # Ensure tables exist
    create_835_export_tables()
    
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        export_id = str(uuid.uuid4())
        
        # Insert into exports_835 table
        cur.execute("""
            INSERT INTO exports_835 (
                id, org_id, export_reference, storage_path, status,
                generated_by, generated_at, error_message
            ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::uuid, %s, %s)
        """, (
            export_id,
            org_id,
            export_reference,
            s3_path,
            'generated',
            generated_by if generated_by else None,
            datetime.datetime.utcnow(),
            None
        ))
        
        # Insert into export_items table
        cur.execute("""
            INSERT INTO export_items (
                export_id, claim_id, payment_id
            ) VALUES (%s::uuid, %s::uuid, %s::uuid)
        """, (
            export_id,
            claim_id,
            claim_json.get('payment_id') if claim_json.get('payment_id') else None
        ))
        
        conn.commit()
        print(f"✅ Stored 835 export data in database with ID: {export_id}")
        return export_id
        
    except Exception as e:
        print(f"❌ Error storing 835 export data in database: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def cleanup_file(file_path: str, delay: int = 0):
    """Clean up generated file after delay"""
    import time
    if delay > 0:
        time.sleep(delay)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ Cleaned up file: {file_path}")
    except Exception as e:
        print(f"⚠️ Could not clean up file {file_path}: {e}")

@router.get("/download/{file_name}")
def download_835_file(file_name: str):
    file_path = f"/tmp/{file_name}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="text/plain", filename=file_name)

# @router.get("/exports", response_model=List[Dict[str, Any]])
# def get_835_exports(org_id: Optional[str] = None, limit: int = 20):
#     """Get list of generated 835 exports from database"""
#     conn = get_pg_conn()
#     cur = conn.cursor()
    
#     try:
#         query = """
#             SELECT 
#                 e.id as export_id,
#                 e.org_id,
#                 e.export_reference,
#                 e.storage_path,
#                 e.status,
#                 e.generated_by,
#                 e.generated_at,
#                 e.error_message,
#                 ei.claim_id,
#                 ei.payment_id,
#                 c.claim_number,
#                 c.patient_name,
#                 c.total_paid_amount,
#                 p.name as payer_name
#             FROM exports_835 e
#             LEFT JOIN export_items ei ON e.id = ei.export_id
#             LEFT JOIN claims c ON ei.claim_id = c.id
#             LEFT JOIN payments py ON c.payment_id = py.id
#             LEFT JOIN payers p ON py.payer_id = p.id
#         """
        
#         params = []
#         if org_id:
#             query += " WHERE e.org_id = %s"
#             params.append(org_id)
            
#         query += " ORDER BY e.generated_at DESC LIMIT %s"
#         params.append(limit)
        
#         cur.execute(query, params)
#         rows = cur.fetchall()
#         columns = [desc[0] for desc in cur.description]
        
#         exports = []
#         for row in rows:
#             export_dict = dict(zip(columns, row))
#             # Convert datetime to string
#             if export_dict.get('generated_at'):
#                 export_dict['generated_at'] = export_dict['generated_at'].isoformat()
#             # Convert decimal to float
#             if export_dict.get('total_paid_amount'):
#                 export_dict['total_paid_amount'] = float(export_dict['total_paid_amount'])
#             exports.append(export_dict)
        
#         return exports
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
#     finally:
#         cur.close()
#         conn.close()

# @router.get("/exports/{export_id}")
# def get_835_export_by_id(export_id: str):
#     """Get specific 835 export data"""
#     conn = get_pg_conn()
#     cur = conn.cursor()
    
#     try:
#         cur.execute("""
#             SELECT 
#                 e.id as export_id,
#                 e.org_id,
#                 e.export_reference,
#                 e.storage_path,
#                 e.status,
#                 e.generated_by,
#                 e.generated_at,
#                 e.error_message,
#                 ei.claim_id,
#                 ei.payment_id,
#                 c.claim_number,
#                 c.patient_name,
#                 c.total_paid_amount,
#                 p.name as payer_name
#             FROM exports_835 e
#             LEFT JOIN export_items ei ON e.id = ei.export_id
#             LEFT JOIN claims c ON ei.claim_id = c.id
#             LEFT JOIN payments py ON c.payment_id = py.id
#             LEFT JOIN payers p ON py.payer_id = p.id
#             WHERE e.id = %s
#         """, (export_id,))
        
#         row = cur.fetchone()
#         if not row:
#             raise HTTPException(status_code=404, detail="835 export not found")
        
#         columns = [desc[0] for desc in cur.description]
#         export_data = dict(zip(columns, row))
        
#         # Convert types for JSON serialization
#         if export_data.get('generated_at'):
#             export_data['generated_at'] = export_data['generated_at'].isoformat()
#         if export_data.get('total_paid_amount'):
#             export_data['total_paid_amount'] = float(export_data['total_paid_amount'])
        
#         return export_data
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
#     finally:
#         cur.close()
#         conn.close()

# @router.post("/exports/{export_id}/download")
# def download_835_from_s3(export_id: str):
#     """Download 835 file from S3 and mark as downloaded"""
#     conn = get_pg_conn()
#     cur = conn.cursor()
    
#     try:
#         # Get export info
#         cur.execute("""
#             SELECT storage_path, export_reference, status
#             FROM exports_835 
#             WHERE id = %s
#         """, (export_id,))
        
#         row = cur.fetchone()
#         if not row:
#             raise HTTPException(status_code=404, detail="Export not found")
        
#         storage_path, export_reference, status = row
        
#         if status == 'failed':
#             raise HTTPException(status_code=400, detail="Export failed, cannot download")
        
#         # Update status to downloaded
#         cur.execute("""
#             UPDATE exports_835 
#             SET status = 'downloaded' 
#             WHERE id = %s AND status != 'downloaded'
#         """, (export_id,))
        
#         conn.commit()
        
#         # Generate presigned URL for secure download
#         s3_key = s3_client.extract_s3_key_from_path(storage_path)
#         presigned_url = s3_client.generate_presigned_url(s3_key, expiration=1800)  # 30 minutes
        
#         if not presigned_url:
#             raise HTTPException(status_code=500, detail="Failed to generate download URL")
        
#         return {
#             "success": True,
#             "s3_path": storage_path,
#             "download_url": presigned_url,
#             "export_reference": export_reference,
#             "expires_in_seconds": 1800,
#             "message": "File marked as downloaded. Use the presigned URL to download the file."
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
#     finally:
#         cur.close()
#         conn.close()
# @router.patch("/exports/{export_id}/status")
# def update_export_status(export_id: str, status: str, error_message: Optional[str] = None):
#     """Update export status"""
    
#     valid_statuses = ['pending', 'generated', 'downloaded', 'failed']
#     if status not in valid_statuses:
#         raise HTTPException(
#             status_code=400, 
#             detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
#         )
    
#     conn = get_pg_conn()
#     cur = conn.cursor()
    
#     try:
#         cur.execute("""
#             UPDATE exports_835 
#             SET status = %s, error_message = %s
#             WHERE id = %s
#         """, (status, error_message, export_id))
        
#         if cur.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Export not found")
        
#         conn.commit()
        
#         return {
#             "success": True,
#             "export_id": export_id,
#             "status": status,
#             "message": f"Export status updated to {status}"
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         conn.rollback()
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
#     finally:
#         cur.close()
#         conn.close()
# @router.get("/debug/claim/{claim_id}")
# def debug_claim_data(claim_id: str):
#     """Debug endpoint to check raw claim data"""
#     try:
#         claim_json = get_claim_json_from_database(claim_id)
#         return {
#             "claim_id": claim_id,
#             "raw_data": claim_json,
#             "data_summary": {
#                 "claim_number": claim_json.get("claim_number"),
#                 "patient_name": claim_json.get("patient_name"),
#                 "member_id": claim_json.get("member_id"),
#                 "payer_name": claim_json.get("payer_name"),
#                 "total_billed": claim_json.get("total_billed_amount"),
#                 "total_paid": claim_json.get("total_paid_amount"),
#                 "payment_amount": claim_json.get("payment_amount"),
#                 "service_lines_count": len(claim_json.get("service_lines", []))
#             }
#         }
#     except Exception as e:
#         return {
#             "error": str(e),
#             "claim_id": claim_id
#         }

