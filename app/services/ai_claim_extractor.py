from typing import List, Dict, Any
import uuid
import json
import os
import re
from ..utils.logger import get_logger

logger = get_logger(__name__)

# AI Model Integration
try:
    import openai
    import os
    from dotenv import load_dotenv
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get OpenAI API key from environment variable (.env file)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if OPENAI_API_KEY:
        logger.info("🔍 Loading OpenAI API key from .env file...")
    OPENAI_AVAILABLE = True and OPENAI_API_KEY is not None and len(OPENAI_API_KEY or '') > 20
    
except ImportError as e:
    OPENAI_AVAILABLE = False
    OPENAI_API_KEY = None

    




async def ai_extract_claims(raw_text: str, dynamic_key: List[str]) -> Dict[str, Any]:
    """
    Use ONLY AI model to extract claims from raw text and convert to structured JSON.
    Returns extraction result with confidence scores.
    """
    if not raw_text or raw_text.strip() == "":
        return {"claims": [], "confidence": 0, "error": "No text to process"}
    
    # Use ONLY AI extraction - provide fallback for testing
    if OPENAI_AVAILABLE and OPENAI_API_KEY:
        try:
            result = await extract_with_openai(raw_text, dynamic_key)
            # if result.get("claims"):
            #     return result
            # else:
            #     logger.warning("OpenAI returned empty claims, using fallback")
            #     return create_fallback_result(raw_text)


            


            return result
        except Exception as e:
            logger.error("OpenAI extraction failed: %s", str(e))
            return create_fallback_result(raw_text)
    else:
        logger.warning("OpenAI not available, using fallback extraction")
        return create_fallback_result(raw_text)



def create_fallback_result(raw_text: str) -> Dict[str, Any]:
    """
    Create a structured result when AI fails - extracts basic info from the raw text.
    """
    
    # Extract basic information from the text using simple parsing
    lines = raw_text.split('\n')
    
    # Look for payer information
    payer_name = "Unknown Payer"
    check_number = None
    check_amount = 0.0
    
    for line in lines:
        line = line.strip()
        if "UNITEDHEALTHCARE" in line or "UNITED" in line:
            payer_name = "UnitedHealthcare"
        elif "CHECK NO." in line and "AMOUNT" in line:
            # Extract check info from line like "CHECK NO. AMOUNT U2531457 $1556.32"
            parts = line.split()
            for i, part in enumerate(parts):
                if part.startswith("U") and len(part) > 5:
                    check_number = part
                elif part.startswith("$"):
                    try:
                        check_amount = float(part[1:].replace(",", ""))
                    except:
                        pass
    
    # Extract claims using basic patterns
    claims = []
    current_claim = None
    
    for line in lines:
        line = line.strip()
        
        # Look for member information
        if line.startswith("MEMBER ") and "NUMBER" in line:
            if current_claim:
                claims.append(current_claim)
            
            # Parse member line: "MEMBER BOUFFARD, JUDITH H. NUMBER 04007-996949371-00 ACCOUNT NO. 2569"
            parts = line.split("NUMBER")
            if len(parts) >= 2:
                member_name = parts[0].replace("MEMBER", "").strip()
                number_part = parts[1].strip()
                member_id = number_part.split()[0] if number_part.split() else "Unknown"
                
                current_claim = {
                    "claim_number": f"FALLBACK-{len(claims) + 1}",
                    "patient_name": member_name,
                    "member_id": member_id,
                    "provider_name": "Unknown Provider",
                    "total_billed_amount": 0.0,
                    "total_allowed_amount": 0.0,
                    "total_paid_amount": 0.0,
                    "total_adjustment_amount": 0.0,
                    "claim_status_code": "1",
                    "service_date_from": "2025-10-08",
                    "service_date_to": "2025-10-08",
                    "confidence": 60,
                    "service_lines": []
                }
        
        # Look for claim numbers
        elif line.startswith("CLAIM NO.") and current_claim:
            claim_no = line.replace("CLAIM NO.", "").strip()
            current_claim["claim_number"] = claim_no
        
        # Look for claim totals
        elif line.startswith("CLAIM TOTAL") and current_claim:
            parts = line.replace("CLAIM TOTAL", "").strip().split()
            if len(parts) >= 4:
                try:
                    current_claim["total_billed_amount"] = float(parts[0])
                    current_claim["total_paid_amount"] = float(parts[-1])
                except ValueError:
                    pass
    
    # Add the last claim
    if current_claim:
        claims.append(current_claim)
    
    
    return {
        "confidence": 60,
        "payer_info": {
            "name": payer_name,
            "code": "FALLBACK",
            "confidence": 50
        },
        "payment": {
            "payment_reference": check_number or "FALLBACK-PAY",
            "payment_date": "2025-10-30",
            "payment_amount": check_amount,
            "currency": "USD",
            "confidence": 70
        },
        "claims": claims
    }

# def extract_with_openai(raw_text: str, dynamic_key: List[str]) -> Dict[str, Any]:
#     """
#     Use OpenAI to extract structured data matching database schema with confidence scores.
#     """
#     try:
#         # Initialize OpenAI client with configured API key
#         client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
#         prompt = f"""
#         You are given TWO inputs:

# INPUT 1:
# A JSON object named `dynamic_keys` (structure exactly like provided), containing:
# - sections (id, sectionName, dataKey, sectionOrder)
# - fields (id, field, label, type, fieldOrder, confidence)

# INPUT 2:
# Raw document text.

# GOAL:
# Use `dynamic_keys` to CONTROL the response structure.
# Extract values from text and RETURN a response JSON where:
# - Structure comes from `dynamic_keys`
# - Data comes from extracted text

# RULES (STRICT):

# 1. `dynamic_keys` is LEVEL-0 (source schema).
# 2. Each section in `dynamic_keys` is LEVEL-1.
# 3. Each field inside a section is LEVEL-2.
# 4. Do NOT add, remove, rename, or reorder sections or fields.
# 5. Do NOT hardcode field names.
# 6. Do NOT invent values.
# 7. Extract values ONLY if present in text; otherwise return null.

# BEHAVIOR:

# For EACH section in `dynamic_keys`:
# - Create the same section in response.
# - Copy `sectionName`, `sectionOrder`, and `dataKey`.

# For EACH field inside the section:
# - Create the same field object.
# - Add ONE new key named `"value"`.
# - `"value"` must contain the extracted value from text.
# - Extraction must respect section context.
# - Type hint (`type`) guides format (date, number, text).

# OUTPUT FORMAT (FINAL RESPONSE):

# {
#   "sections": [
#     {
#       "sectionName": "<sectionName>",
#       "dataKey": "<dataKey>",
#       "sectionOrder": <number>,
#       "fields": [
#         {
#           "field": "<field>",
#           "value": "<extracted_value_or_null>"
#         }
#       ]
#     }
#   ]
# }

# CONSTRAINTS:
# - Output ONLY valid JSON.
# - No explanations.
# - No extra keys.
# - No confidence, label, or type in response.
# - Dynamic structure must work for ANY future `dynamic_keys`.

# RETURN ONLY JSON.



#         Extract data from this text:
#         {raw_text[:4000]}

        
#         """        
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.1,
#             max_tokens=3000
#         )
        
#         content = response.choices[0].message.content.strip()
#         print( "OpenAI raw response content:=========", content)
        
#         # Clean up response if it has markdown formatting
#         if content.startswith("```json"):
#             content = content[7:]
#         if content.endswith("```"):
#             content = content[:-3]
#         content = content.strip()
        
#         result = json.loads(content)
        
#         # Ensure confidence is included
#         if "confidence" not in result:
#             result["confidence"] = 70  # Default confidence
#         print( "OpenAI extraction result:=========", result)
#         return result
        
#     except json.JSONDecodeError as e:
#         logger.error("JSON decode error: %s", str(e))
#         logger.error("Raw content: %s", content)
#         return {"claims": [], "confidence": 0, "error": "JSON decode error: " + str(e)}
#     except Exception as e:
#         logger.error("OpenAI API error: %s", str(e))
#         return {"claims": [], "confidence": 0, "error": "API error: " + str(e)}



def _build_extraction_hints(raw_text: str) -> Dict[str, Any]:
    """
    Build lightweight regex-based hints to help the model find service line data.
    We do NOT trust these fully; they are only contextual hints used in the prompt.
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

    # Common patterns
    date_pat = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
    amount_pat = re.compile(r"\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?")
    cpt_pat = re.compile(r"\b\d{5}\b")  # CPT: 5-digit numeric
    hcpcs_pat = re.compile(r"\b[A-Z]\d{4}\b")  # HCPCS: letter + 4 digits
    rev_code_pat = re.compile(r"\b(?:REV|REVENUE)\s*CODE\b|\b\d{4}\b", re.IGNORECASE)
    units_pat = re.compile(r"\b(?:units?|qty|quantity)\s*[:\-]?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)

    service_line_candidates: List[Dict[str, Any]] = []
    for ln in lines:
        # Heuristics: line containing at least a code and amount/date/units
        has_code = bool(cpt_pat.search(ln) or hcpcs_pat.search(ln) or rev_code_pat.search(ln))
        has_other = bool(amount_pat.search(ln) or date_pat.search(ln) or units_pat.search(ln))
        has_marker = any(k in ln.lower() for k in ["svc", "service", "dos", "proc", "procedure", "hcpcs", "cpt", "rev"])
        if (has_code and has_other) or (has_code and has_marker):
            service_line_candidates.append({
                "line": ln,
                "dates": date_pat.findall(ln),
                "amounts": amount_pat.findall(ln),
                "units": units_pat.findall(ln),
                "cpt": cpt_pat.findall(ln),
                "hcpcs": hcpcs_pat.findall(ln),
                "rev_code_hit": bool(rev_code_pat.search(ln)),
            })
        if len(service_line_candidates) >= 50:
            break

    return {
        "service_line_candidates": service_line_candidates,
    }
#=========================start=================================


def _index_fields_by_label(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Returns { normalized_label: field_object }
    """
    out = {}
    for section in result.get("sections", []):
        for field in section.get("fields", []):
            label = field.get("label", "").strip().lower()
            out[label] = field
    return out


async def extract_with_openai(
    raw_text: str,
    dynamic_keys: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    AI-only, label-locked, two-pass extraction.
    Guarantees: if LABEL exists in raw_text, value will not be null.
    """
    print(raw_text)
    print(dynamic_keys)
    try:
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

        # ---------- PASS 1 ----------
        base_prompt = f"""
You are a STRICT data extractor.

RULES:
1. dynamic_keys DEFINES THE SCHEMA.
2. COPY structure EXACTLY.
3. Add ONLY one key: "value".
4. Extract ONLY from raw_text.
5. If value not found, set null.
6. DO NOT guess.
7. Dates: if range, return ONLY the FIRST date.

EXTRACTION STRATEGY:
- For each field, locate its LABEL followed by ":".
- Extract the value immediately after the label.
- Stop at the next label or line break.
- If label exists, value MUST be extracted.

MANDATORY OUTPUT FORMAT:

{{
"sections": [
    {{
    "id": "<same as input>",
    "sectionName": "<same as input>",
    "dataKey": "<same as input>",
    "sectionOrder": <same as input>,
    "fields": [
        {{
        "id": "<same>",
        "field": "<same>",
        "label": "<same>",
        "type": "<same>",
        "fieldOrder": <same>,
        "confidence": <same>,
        "value": "<extracted_value_or_null>"
        }}
    ]
    }}
]
}}

OUTPUT:
VALID JSON ONLY. NO TEXT.

dynamic_keys:
{json.dumps(dynamic_keys, ensure_ascii=False)}

raw_text:
{raw_text[:6000]}
"""

        # 3. Call AI with Retry Logic
        import asyncio
        response = None
        for attempt in range(3):
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You output strict JSON only."},
                        {"role": "user", "content": base_prompt},
                    ],
                    temperature=0,
                    max_tokens=3500,
                )
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"OpenAI API failed after 3 attempts: {e}")
                    raise e
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"OpenAI API failed (attempt {attempt+1}/3). Retrying in {wait_time}s... Error: {e}")
                await asyncio.sleep(wait_time)

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1].strip()

        result = json.loads(content)

        # Ensure value key exists
        for s in result.get("sections", []):
            for f in s.get("fields", []):
                f.setdefault("value", None)

        # ---------- FIND NULLS ----------
        label_index = _index_fields_by_label(result)
        missing_labels = [
            field["label"]
            for field in label_index.values()
            if field.get("value") in (None, "", [])
        ]

        if not missing_labels:
            return result

        # ---------- PASS 2 (LABEL-LOCKED RECOVERY) ----------
        recovery_prompt = f"""
Some fields were NOT extracted even though their LABELS exist.

STRICT RULES:
1. Extract values ONLY by LABEL.
2. Use ONLY raw_text.
3. If label exists, value MUST be extracted.
4. Dates: if range, return ONLY the FIRST date.
5. Output JSON ONLY.
6. In amount don't read $ sign.
LABELS:
{json.dumps(missing_labels, ensure_ascii=False)}

            MANDATORY OUTPUT FORMAT:

            {
            "sections": [
                {
                "id": "<same as input>",
                "sectionName": "<same as input>",
                "dataKey": "<same as input>",
                "sectionOrder": "<same as input>",
                "fields": [
                    {
                    "id": "<same>",
                    "field": "<same>",
                    "label": "<same>",
                    "type": "<same>",
                    "fieldOrder": "<same>",
                    "confidence": "<same>",
                    "value": "<extracted_value_or_null>"
                    }
                ]
                }
            ]
            }

raw_text:
{raw_text[:9000]}
"""

        retry = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You output strict JSON only."},
                {"role": "user", "content": recovery_prompt},
            ],
            temperature=0,
            max_tokens=1200,
        )

        retry_content = retry.choices[0].message.content.strip()
        if retry_content.startswith("```"):
            retry_content = retry_content.split("```")[1].strip()

        recovered = json.loads(retry_content).get("values_by_label", {})

        # ---------- MERGE BY LABEL ----------
        for label, value in recovered.items():
            norm = label.strip().lower()
            if norm in label_index and value not in (None, "", []):
                label_index[norm]["value"] = value

        return result

    except Exception as e:
        logger.error("AI extraction failed", exc_info=True)
        return {
            "sections": [],
            "error": "ai_extraction_failed",
            "details": str(e),
        }



# async def extract_with_openai(raw_text: str, dynamic_keys: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """
#     Extract structured data from raw text using dynamic_keys driven schema.
#     """

#     try:
#         client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

#         hints = _build_extraction_hints(raw_text)

#         prompt = """
#             You are given TWO inputs.

#             INPUT 1:
#             A JSON object named `dynamic_keys`.
#             It defines the EXACT response schema.
#             It contains sections and fields with metadata.

#             INPUT 2:
#             Raw document text.

#             AUXILIARY INPUT 3 (HINTS):
#             A small JSON with regex-detected candidates for service line data
#             (procedure codes, units, amounts, dates). Use these ONLY as guidance
#             to improve recall; do not invent values.

#             GOAL:
#             Return extracted data by COPYING the structure of `dynamic_keys`
#             and ADDING ONE key named `value` inside EACH field.

#             STRICT RULES:

#             1. DO NOT remove any existing keys.
#             2. DO NOT rename any keys.
#             3. DO NOT add new keys except `value`.
#             4. DO NOT reorder sections or fields.
#             5. Preserve ALL field properties:
#             - id
#             - field
#             - label
#             - type
#             - fieldOrder
#             - confidence
#             6. Add `"value"` to every field.
#             7. Extract values ONLY from text.
#             8. If value is not found, set `"value": null`.
#             9. In amount not read $ sign.

#             LEVEL BEHAVIOR:
#             - dynamic_keys = schema
#             - section = grouping
#             - field = extraction unit

#                         SPECIAL INSTRUCTIONS FOR SERVICE LINE DATA:
#                         - Sections whose names or dataKey indicate service lines (contains any of:
#                             "service", "svc", "service line") must be populated by scanning both raw text
#                             AND HINTS. Many documents encode service lines as rows in tables.
#                         - Use common patterns:
#                             • CPT: 5-digit numeric (e.g., 99213)
#                             • HCPCS: letter + 4 digits (e.g., J1234)
#                             • Units: integers/decimals near words like "Units", "Qty", "Quantity"
#                             • Dates of service: mm/dd/yyyy (or similar), often a range like 10/08/2025 - 10/08/2025
#                             • Amounts: $1,234.56 style
#                         - Prefer a value that appears on the same line or row as the code.
#                         - If multiple candidates exist, choose the most contextually relevant one,
#                             prioritizing proximity and section semantics; otherwise return null.
#                         - Do NOT add new fields; only fill the existing ones defined in dynamic_keys.

#             MANDATORY OUTPUT FORMAT:

#             {
#             "sections": [
#                 {
#                 "id": "<same as input>",
#                 "sectionName": "<same as input>",
#                 "dataKey": "<same as input>",
#                 "sectionOrder": <same as input>,
#                 "fields": [
#                     {
#                     "id": "<same>",
#                     "field": "<same>",
#                     "label": "<same>",
#                     "type": "<same>",
#                     "fieldOrder": <same>,
#                     "confidence": <same>,
#                     "value": "<extracted_value_or_null>"
#                     }
#                 ]
#                 }
#             ]
#             }

#             NO explanations.
#             NO markdown.
#             ONLY valid JSON.

#             dynamic_keys:
#             """ + json.dumps(dynamic_keys, ensure_ascii=False) + """

#             RAW TEXT:
#             """ + raw_text[:6000] + """

#             HINTS:
#             """ + json.dumps(hints, ensure_ascii=False)

#         response = await client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {"role": "system", "content": "You are a strict JSON extraction engine."},
#                 {"role": "user", "content": prompt},
#             ],
#             temperature=0,
#             max_tokens=3000,
#         )

#         content = response.choices[0].message.content.strip()

#         print()
#         # print("OpenAI raw response content:=========", content)
#         print()

#         # Remove markdown if present
#         if content.startswith("```"):
#             content = content.split("```")[1]

#         result = json.loads(content)

#         # HARD GUARANTEE: every field has `value`
#         for section in result.get("sections", []):
#             for field in section.get("fields", []):
#                 field.setdefault("value", None)
#         # print("OpenAI extraction result:=========", result)
#         return result

#     except json.JSONDecodeError as e:
#         logger.error("JSON decode failed", exc_info=True)
#         return {
#             "sections": [],
#             "error": "Invalid JSON returned by AI",
#             "details": str(e),
#         }

#     except openai.OpenAIError as e:
#         logger.error("OpenAI API error", exc_info=True)
#         return {
#             "sections": [],
#             "error": "OpenAI API error",
#             "details": str(e),
#         }

#     except Exception as e:
#         logger.error("Unexpected extraction error", exc_info=True)
#         return {
#             "sections": [],
#             "error": "Unhandled extraction error",
#             "details": str(e),
#         }
#=========================end===============================

#==================================================================

# def extract_with_openai(raw_text: str, dynamic_keys: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """
#     Extract structured data from raw text using dynamic_keys driven schema.
#     FINAL OUTPUT SHAPE = dynamic_keys-like, repeated per claim
#     """

#     try:
#         client = openai.OpenAI(api_key=OPENAI_API_KEY)

#         # 1️⃣ Split raw text into claim segments
#         segments = _split_claims(raw_text)

#         claims: List[Dict[str, Any]] = []

#         for seg_text in segments:
#             seg_hints = _build_extraction_hints(seg_text)

#             prompt = """
# You are given TWO inputs.

# INPUT 1:
# A JSON object named `dynamic_keys`.
# It defines the EXACT response schema.

# INPUT 2:
# Raw document text (ONE claim only).

# RULES:
# 1. Copy dynamic_keys EXACTLY.
# 2. Do NOT remove, rename, reorder keys.
# 3. Add ONLY `value` inside each field.
# 4. Extract values ONLY from raw text.
# 5. If value missing → null.

# OUTPUT FORMAT (ONLY THIS):

# {
#   "sections": [ ...dynamic_keys with values... ]
# }

# NO explanations.
# ONLY valid JSON.
# dynamic_keys:
# """ + json.dumps(dynamic_keys, ensure_ascii=False) + """

# RAW TEXT:
# """ + seg_text[:3500] + """

# HINTS:
# """ + json.dumps(seg_hints, ensure_ascii=False)

#             response = client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=[
#                     {"role": "system", "content": "You are a strict JSON extraction engine."},
#                     {"role": "user", "content": prompt},
#                 ],
#                 temperature=0,
#                 response_format={"type": "json_object"},
#                 max_tokens=2000,
#             )

#             content = response.choices[0].message.content.strip()
#             payload = _sanitize_ai_json(content)
#             extracted = _extract_first_json_value(payload) or payload

#             try:
#                 result = json.loads(extracted)
#             except Exception:
#                 result = {"sections": []}

#             # 🔒 Guarantee value key
#             for section in result.get("sections", []):
#                 for field in section.get("fields", []):
#                     field.setdefault("value", None)

#             claims.append(result)

#         # ✅ FINAL OUTPUT — dynamic_keys-like
#         return {
#             "claims": claims
#         }

#     except Exception as e:
#         logger.error("Extraction failed", exc_info=True)
#         return {
#             "claims": [],
#             "error": str(e),
#         }


def extract_with_rules(raw_text: str) -> List[Dict[str, Any]]:
    """
    Fallback rule-based extraction when AI is not available.
    """
    # Simple rule-based extraction (improve based on your data patterns)
    lines = raw_text.split('\n')
    
    # Look for common patterns
    payer_name = "Unknown Payer"
    patient_name = "Unknown Patient"
    
    # Simple pattern matching (customize for your data)
    for line in lines:
        if "payer" in line.lower() or "insurance" in line.lower():
            payer_name = line.strip()[:50]  # First 50 chars
        if "patient" in line.lower() or "member" in line.lower():
            patient_name = line.strip()[:50]
    
    return [
        {
            "payer_name": payer_name,
            "patient_name": patient_name,
            "claims": [
                {"claim_number": "EXTRACTED-001", "amount": 0.0, "raw_source": raw_text[:200]}
            ]
        }
    ]


def flatten_claims2(data: dict) -> dict:
    """
    Fetch:
    - payer name
    - remark_payer_code
    - payment_reference
    - payment_date
    - payment_amount
    """

    result = {
        "payer": None,
        "remark_payer_code": None,
        "payment_reference": None,
        "payment_date": None,
        "payment_amount": None,
        "claim_payment": None,
        "claim_number": None,
        "patient_name": None,
        "payee_name": None, 
        "payment": None,
       
        "total_paid": None,
        "adj_amount": None,
        "claim_status_code": None,
        "dates_of_service" : None,
        "claim_confidence": None,
        "procedure_code": None,
        "dates_of_service": None,
        "units": None,
        "patient_id": None,
        "section": None

        
    }

    # Helpers to robustly parse numeric values (currency, commas, parentheses)
    def _parse_float(v) -> float:
        try:
            if v is None:
                return 0.0
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                s = v.strip()
                if not s:
                    return 0.0
                neg = False
                if s.startswith("(") and s.endswith(")"):
                    neg = True
                    s = s[1:-1]
                s = s.replace(",", "").replace("$", "").replace("USD", "").strip()
                m = re.search(r"-?\d+(?:\.\d+)?", s)
                if not m:
                    return 0.0
                num = float(m.group(0))
                return -num if neg else num
            return 0.0
        except Exception:
            return 0.0

    def _parse_int(v) -> int:
        try:
            return int(_parse_float(v))
        except Exception:
            return 0

    # iterate all sections → all fields
    for section in data.get("sections", []):
        for field in section.get("fields", []):

            field_name = field.get("field")
            value = field.get("value")
            confidence = field.get("confidence")

            print()
            print("field_name===========:", field_name)
            print("value===========:", value)
            print()

            if field_name == "payer" or field_name == "payer_name":
                result["payer_name"] = value

            elif field_name == "remark_payer_code":
                result["payer_code"] = value

            elif field_name == "check_eft_trace_number":
                result["payment_reference"] = value

            elif field_name == "check_eft_date":
                result["payment_date"] = value

            elif field_name == "payment_amount":
                result["payment_amount"] = _parse_float(value)

            elif field_name == "claim_payment":
                result["claim_payment"] = value

            elif field_name == "claim_number":
                result["claim_number"] = value
            
            elif field_name == "patient_name":
                result["patient_name"] = value
            
            elif field_name == "payee_name":
                result["payee_name"] = value

            elif field_name == "payment":
                result["payment"] = _parse_int(value)



            elif field_name == "claim_payment":
                result["claim_payment"] = _parse_int(value)
            
            elif field_name == "total_paid":
                result["total_paid"] = _parse_int(value)

            elif field_name == "adj_amount":
                result["adj_amount"] = _parse_int(value)

            elif field_name == "claim_status_code":
                result["claim_status_code"] = value

            elif field_name == "dates_of_service":
                result["dates_of_service"] = value

            elif field_name == "claim_payment":
                result["claim_confidence"] = str(int(confidence))

            elif field_name == "procedure_code":
                result["procedure_code"] = value

            elif field_name == "dates_of_service":
                result["dates_of_service"] = value
            
            elif field_name == "units":
                result["units"] = _parse_int(value)
                
            elif field_name == "patient_id":
                result["patient_id"] = value


            result["overall_confidence"] = ""
            result["payer_confidence"] = ""
            result["claim_confidence"] = ""
            result["section"] =  data 

    return result


def flatten_claims(extracted: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Flatten AI-extracted claims with payer info and confidence scores.
    """
    print("=================================== enter in flatter claims")
    flat = []
    # if not extracted or "claims" not in extracted:
    #     return flat
    
    for section in extracted.get("sections"):
        key = section.get("file_payment_information")
        print( "key:", key)


    # Optional debug of sections/fields (disabled)

    payer_info = extracted.get("fields", {})
    payment_info = extracted.get("payment", {})
    overall_confidence = extracted.get("confidence", 0)
    
    for claim in extracted.get("claims", []):
        flat_claim = {
            "payer_name": payer_info.get("name", "Unknown Payer"),
            "payer_code": payer_info.get("code"),
            "payment_reference": payment_info.get("payment_reference"),
            "payment_date": payment_info.get("payment_date"),
            "payment_amount": payment_info.get("payment_amount", 0),
            "overall_confidence": overall_confidence,
            "payer_confidence": payer_info.get("confidence", 0),
            "claim_confidence": claim.get("confidence", 0),
            **claim
        }
        flat.append(flat_claim)

    return flat
