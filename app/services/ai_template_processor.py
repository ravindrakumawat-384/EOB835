from typing import List, Dict, Any
import json
import re
from ..utils.logger import get_logger
from openai import OpenAI

logger = get_logger(__name__)

# AI Model Integration for dynamic key extraction
try:
    import openai
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_AVAILABLE = True and OPENAI_API_KEY is not None and len(OPENAI_API_KEY or '') > 20
    
except ImportError as e:
    OPENAI_AVAILABLE = False
    OPENAI_API_KEY = None

async def process_template_with_dynamic_extraction(raw_text: str) -> Dict[str, Any]:
    """
    Complete template processing with dynamic key extraction and JSON conversion.
    """
    try:
        # Clean text of any problematic characters
        if '\x00' in raw_text:
            logger.warning(f"Cleaning NUL bytes from text for file: {filename}")
            raw_text = raw_text.replace('\x00', '')
        
        # Remove other problematic characters that might cause issues
        raw_text = ''.join(char for char in raw_text if ord(char) >= 32 or char in '\n\r\t')
        
        # Step 1: Extract dynamic keys from text
        dynamic_keys = extract_dynamic_keys_from_text(raw_text)
        logger.info(f"Extracted {dynamic_keys} dynamic keys")
        
        # # Step 2: Convert text to JSON using dynamic keys
        # json_result = convert_text_to_dynamic_json(raw_text, dynamic_keys, filename)
        
        # # Step 3: Organize results according to database schema
        # # Only keep the first claim if multiple are present
        # claims = json_result.get("claims", [])
        # if isinstance(claims, list) and len(claims) > 1:
        #     json_result["claims"] = [claims[0]]

        # # Add payer details to each claim if available
        # payer_fields = [
        #     "payer_name", "payer_code", "insurance_company", "insurer", "carrier",
        #     "insurance_carrier", "plan_name", "health_plan", "insurance_plan",
        #     "company_name", "organization_name", "insurance_name"
        # ]
        # payer_info = {}
        # for field in payer_fields:
        #     val = json_result.get(field)
        #     if val:
        #         payer_info[field] = val
        # # If payer info found, add to each claim
        # if payer_info and "claims" in json_result and isinstance(json_result["claims"], list):
        #     for claim in json_result["claims"]:
        #         claim["payer"] = payer_info

        result = {
            "dynamic_keys": dynamic_keys,
            # "extraction_data": json_result,
            # "payments": json_result.get("payments", []),
            # "claims": json_result.get("claims", []),
            # "service_lines": json_result.get("service_lines", []),
            # "raw_key_value_pairs": json_result.get("raw_key_value_pairs", {})
        }

        return result
        
    except Exception as e:
        logger.error(f"Error in template processing: {e}")
        return {
            "dynamic_keys": [],
            # "extraction_data": {},
            # "payments": [],
            # "claims": [],
            # "service_lines": [],
            # "raw_key_value_pairs": {}
        }


# def extract_dynamic_keys_from_text(raw_text: str) -> list:
#     """
#     Use AI to dynamically identify section-wise template fields
#     from a medical document for frontend template generation.
#     """
#     print("Under extract_dynamic_keys_from_text")

#     if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
#         return extract_keys_fallback(raw_text)

#     try:
#         # Clean text
#         clean_text = raw_text.replace("\x00", "").replace("\r", "\n")
#         clean_text = clean_text.encode("utf-8", errors="ignore").decode("utf-8")

#         client = openai.OpenAI(api_key=OPENAI_API_KEY)

#         prompt = f"""
#         You are a medical document section-aware extraction engine.

#         INPUT:
#         OCR text from ONE medical document (PDF/Image/DOC).

#         TASK:
#         Generate a SECTION-WISE TEMPLATE SCHEMA for frontend rendering.

#         RULES (STRICT):
#         1. Identify sections:
#         - File / Payment Information
#         - Claim Information
#         - Service Line Details
#         2. Extract ONLY field metadata (no values).
#         3. Preserve label meaning from the document.
#         4. Do NOT normalize across files.
#         5. Assign UI input type based on data nature.
#         6. Include confidence score (1–100).
#         7.
#         7. Output VALID JSON only.

#         OUTPUT FORMAT (JSON ONLY):

#         {{
#         "sections": [
#             {{
#             "sectionName": "File / Payment Information",
#             "sectionOrder": 1,
#             "fields": [
#                 {{
#                 "id": "payer",
#                 "field": "payer",
#                 "label": "Payer",
#                 "type": "inputText",
#                 "fieldOrder": 1,
#                 "confidence": 0.97,
#                 "validations": [{"required": true}],
#                 "placeholder": "Enter payer name"
#                 }}
#             ]
#             }},
#             {{
#             "sectionName": "Claim Information",
#             "sectionOrder": 2,
#             "fields": [
#                 {{
#                 "id": "patient-name",
#                 "field": "patient_name",
#                 "label": "Patient Name",
#                 "type": "inputText",
#                 "fieldOrder": 1,
#                 "confidence": 0.98,
#                 "validations": [{"required": true}],
#                 "placeholder": "Enter patient name"
#                 }}
#             ]
#             }},
#             {{
#             "sectionName": "Service Line Details",
#             "sectionOrder": 3,
#             "fields": [
#                 {{
#                 "id": "line-control-number",
#                 "field": "line_control_number",
#                 "label": "Line Control Number",
#                 "type": "inputNumber",
#                 "fieldOrder": 1,
#                 "confidence": 0.97,
#                 "validations": [{"required": true}],
#                 "placeholder": "Enter line control number"
#                 }}
#             ]
#             }}
#         ]
#         }}

#         CONSTRAINTS:
#         - No explanations
#         - No markdown
#         - No trailing commas
#         - Valid JSON only

#         TEXT:
#         {clean_text[:5000]}
#         """

#         response = client.chat.completions.create(
#             model="gpt-4.1mini",
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.1,
#             max_tokens=1000
#         )

#         content = response.choices[0].message.content.strip()

#         # Remove accidental markdown
#         if content.startswith("```"):
#             content = content.split("```")[1].strip()

#         data = json.loads(content)

#         if isinstance(data, dict) and "sections" in data:
#             return data["sections"]

#         logger.warning("Unexpected AI response structure")
#         return extract_keys_fallback(raw_text)

#     except json.JSONDecodeError as je:
#         logger.error(f"JSON decode error: {je}")
#         return extract_keys_fallback(raw_text)

#     except Exception as e:
#         logger.error(f"AI key extraction failed: {e}")
#         return extract_keys_fallback(raw_text)


#===========================================================================================

def extract_dynamic_keys_from_text(raw_text: str) -> dict:
    print("Under the function extract_level_names")
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""
            You are a STRICT JSON GENERATOR.

            DOCUMENT TYPE:
            Medical EOB / Remittance PDF (OCR text provided).

            TASK:
            1. Extract the PAYER NAME from the document.
            2. Extract logical level names (headings, subheadings, table headers)
            and FORMAT them into a SECTION-WISE TEMPLATE SCHEMA.

            PAYER NAME RULES:
            - Payer name is the insurance / payer organization name
            - Usually appears at the top of the document or payment header
            - Extract EXACT text
            - If not found, return null
            - Do NOT invent

            SECTIONS (FIXED, DO NOT CHANGE):
            1. File / Payment Information
            2. Claim Information
            3. Service Line Details

            LEVEL DEFINITION:
            A level is any visible structural heading, section title, subsection title,
            table title, or column header that groups data.

            INCLUDE:
            - Page-level headings
            - Section titles
            - Subsection titles
            - Table titles
            - Column headers inside tables

            EXCLUDE:
            - Field values
            - Row data
            - Numbers used only as values
            - Duplicate labels (keep first occurrence only)
            - payer name should be show before comma 

            MAPPING RULES:
            - Assign each extracted label to the MOST RELEVANT section
            - Do NOT invent labels
            - Preserve logical order
            - Table-related labels MUST go under "Service Line Details"

            FIELD RULES (HARD CONTRACT):
            Each field MUST contain EXACTLY:
            - id should be a field name
            - field should be a field name
            - label 
            - type (inputText | inputNumber | inputDate)
            - fieldOrder
            - confidence (1–100)
            - validations (array)
            - placeholder (string)

            OUTPUT RULES:
            - JSON only
            - No markdown
            - No comments
            - No trailing commas
            - Exact key names
            - Exact nesting

            OUTPUT FORMAT (MUST MATCH EXACTLY):

            {{
            "payerName": "string | null",
            "sections": [
                {{
                "id": "<id>",   
                "sectionName": "Payment Information",
                "sectionOrder": 1,
                "dataKey": "payment_information",
                "fields": []
                }},
                {{
                "id": "<id>",  
                "sectionName": "Claim Information",
                "sectionOrder": 2,
                "dataKey": "claim_information",
                "fields": []
                }},
                {{
                "id": "<id>",   
                "sectionName": "Service Line Details",
                "sectionOrder": 3,
                "dataKey": "service_line_details",
                "fields": []
                }}
            ]
            }}

            TEXT TO ANALYZE:
            <<<
            {raw_text[:5000]}
            >>>
            """

        response = client.responses.create(
            model="gpt-5.2",
            temperature=0,
            input=prompt
        )

        content = response.output[0].content[0].text.strip()
        # print("content", content)
        if content.startswith("```"):
            content = content.split("```")[1].strip()
            if content.startswith("json"):
                content = content[4:].strip()

        data = json.loads(content)

        # if isinstance(data, dict) and "sections" in data:
        return data

        # logger.warning("Unexpected AI response structure")
        # return extract_keys_fallback(raw_text)

    except Exception as e:
        logger.error(f"AI key extraction failed: {e}")
        # return extract_keys_fallback(raw_text)

#===========================================================================================

# def extract_dynamic_keys_from_text(raw_text: str) -> list:
#     """
#     Use AI to dynamically identify section-wise template fields
#     from a medical document for frontend template generation.
#     """
#     print("Under extract_dynamic_keys_from_text")

#     if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
#         return extract_keys_fallback(raw_text)

#     try:
#         clean_text = (
#             raw_text.replace("\x00", "")
#             .replace("\r", "\n")
#             .encode("utf-8", errors="ignore")
#             .decode("utf-8")
#         )

#         client = openai.OpenAI(api_key=OPENAI_API_KEY)

#         prompt = f"""
#                 You are a STRICT JSON GENERATOR.

#                 Your task is to OUTPUT A JSON OBJECT THAT MATCHES THE SCHEMA BELOW EXACTLY.

#                 ⚠️ THIS IS NOT AN EXAMPLE.
#                 ⚠️ THIS IS A HARD CONTRACT.
#                 ⚠️ DO NOT ADD, REMOVE, OR RENAME KEYS.

#                 DOCUMENT TYPE:
#                 Medical EOB / Remittance / Claim document.

#                 TASK:
#                 Generate a SECTION-WISE TEMPLATE SCHEMA for frontend form rendering.
#                 Extract ONLY metadata (no values).

#                 SECTIONS (FIXED):
#                 1. File / Payment Information
#                 2. Claim Information
#                 3. Service Line Details

#                 FIELD RULES:
#                 - Each field MUST include:
#                 id, field, label, type, fieldOrder, confidence, validations, placeholder
#                 - confidence MUST be an INTEGER between 1 and 100
#                 - type MUST be one of:
#                 inputText | inputNumber | inputDate
#                 - validations MUST be an array
#                 - placeholder MUST be a string
#                 - Do NOT invent labels that do not appear in the document
#                 - Do NOT mix data between sections

#                 ⚠️ OUTPUT JSON SCHEMA (MUST MATCH EXACTLY):

#                 {{
#                 "sections": [
#                     {{
#                     "sectionName": "File / Payment Information",
#                     "sectionOrder": 1,
#                     "fields": [
#                         {{
#                         "id": "payer",
#                         "field": "payer",
#                         "label": "Payer",
#                         "type": "inputText",
#                         "fieldOrder": 1,
#                         "confidence": 99,
#                         "validations": [
#                             { "required": true }
#                         ],
#                         "placeholder": "Enter your payer"
#                         }}
#                     ]
#                     }},
#                     {{
#                     "sectionName": "Claim Information",
#                     "sectionOrder": 2,
#                     "fields": [
#                         {{
#                         "id": "patient-name",
#                         "field": "patient_name",
#                         "label": "Patient Name",
#                         "type": "inputText",
#                         "fieldOrder": 1,
#                         "confidence": 99,
#                         "validations": [
#                             { "required": true }
#                         ],
#                         "placeholder": "Enter patient name"
#                         }}
#                     ]
#                     }},
#                     {{
#                     "sectionName": "Service Line Details",
#                     "sectionOrder": 3,
#                     "fields": [
#                         {{
#                         "id": "line-ctrl-number",
#                         "field": "line_ctrl_number",
#                         "label": "Line Control Number",
#                         "type": "inputNumber",
#                         "fieldOrder": 1,
#                         "confidence": 98,
#                         "validations": [
#                             { "required": true }
#                         ],
#                         "placeholder": "Enter line control number"
#                         }}
#                     ]
#                     }}
#                 ]
#                 }}
                
#                 CONSTRAINTS:
#                 - JSON only
#                 - No markdown
#                 - No comments
#                 - No trailing commas
#                 - Exact key names
#                 - Exact nesting

#                 TEXT TO ANALYZE:
#                 {clean_text[:5000]}
#                 """

#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.1,
#             max_tokens=1200
#         )

#         content = response.choices[0].message.content.strip()

#         if content.startswith("```"):
#             content = content.split("```")[1].strip()

#         data = json.loads(content)

#         if isinstance(data, dict) and "sections" in data:
#             return data["sections"]

#         logger.warning("Unexpected AI response structure")
#         return extract_keys_fallback(raw_text)

#     except Exception as e:
#         logger.error(f"AI key extraction failed: {e}")
#         return extract_keys_fallback(raw_text)



# def extract_keys_fallback(raw_text: str) -> List[Dict[str, Any]]:
#     """
#     Fallback method to extract keys and return structured sections format
#     when AI is not available. Returns the same structure as AI extraction.
#     """
#     # Initialize section containers
#     payment_fields = []
#     claim_fields = []
#     service_line_fields = []
    
#     lines = raw_text.split('\n')
#     text_lower = raw_text.lower()
    
#     # Helper function to determine field type from key/value
#     def infer_field_type(key: str, value: str = "") -> str:
#         key_lower = key.lower()
#         value_lower = value.lower() if value else ""
        
#         # Date fields
#         if any(d in key_lower for d in ['date', 'dob', 'dos', 'time', 'period']):
#             return "inputDate"
#         # Numeric/Amount fields    
#         if any(a in key_lower for a in ['amount', 'charge', 'payment', 'paid', 'billed', 'total', 'units', 'quantity', 'number', 'count', 'id', 'code']):
#             if any(c in key_lower for c in ['code', 'id', 'number', 'reference']):
#                 return "inputText"
#             return "inputNumber"
#         # Default to text
#         return "inputText"
    
#     # Helper function to convert key to label
#     def key_to_label(key: str) -> str:
#         return ' '.join(word.capitalize() for word in key.replace('_', ' ').replace('-', ' ').split())
    
#     # Common patterns for key-value extraction
#     patterns = [
#         r'([A-Za-z][A-Za-z\s]+):',  # "Label:" pattern
#         r'([A-Za-z][A-Za-z\s]+)\s*=',  # "Label =" pattern
#     ]
    
#     extracted_keys = set()
    
#     # Extract potential keys using regex patterns
#     for line in lines:
#         line = line.strip()
#         if len(line) < 3:
#             continue
            
#         for pattern in patterns:
#             matches = re.findall(pattern, line)
#             for match in matches:
#                 # Clean up the key
#                 key = match.strip().lower()
#                 key = re.sub(r'[^a-zA-Z0-9\s]', '', key)  # Remove special chars
#                 key = '_'.join(key.split())  # Convert to snake_case
                
#                 if len(key) > 2 and len(key) < 50:  # Reasonable key length
#                     extracted_keys.add(key)
    
#     # Categorize keys into sections based on content
#     payment_keywords = ['payment', 'payer', 'check', 'eft', 'trace', 'transaction', 'remit']
#     claim_keywords = ['claim', 'patient', 'member', 'provider', 'subscriber', 'policy', 'group', 'insured']
#     service_keywords = ['service', 'line', 'procedure', 'cpt', 'modifier', 'units', 'charge', 'dos']
    
#     field_order_payment = 1
#     field_order_claim = 1
#     field_order_service = 1
    
#     for key in extracted_keys:
#         field_type = infer_field_type(key)
#         label = key_to_label(key)
#         confidence = 0.75  # Lower confidence for fallback extraction
        
#         field_obj = {
#             "field": key,
#             "label": label,
#             "type": field_type,
#             "confidence": confidence
#         }
        
#         # Categorize by keywords
#         if any(kw in key for kw in service_keywords):
#             field_obj["fieldOrder"] = field_order_service
#             service_line_fields.append(field_obj)
#             field_order_service += 1
#         elif any(kw in key for kw in claim_keywords):
#             field_obj["fieldOrder"] = field_order_claim
#             claim_fields.append(field_obj)
#             field_order_claim += 1
#         elif any(kw in key for kw in payment_keywords):
#             field_obj["fieldOrder"] = field_order_payment
#             payment_fields.append(field_obj)
#             field_order_payment += 1
#         else:
#             # Default to claim section for unknown keys
#             field_obj["fieldOrder"] = field_order_claim
#             claim_fields.append(field_obj)
#             field_order_claim += 1
    
#     # Add common expected fields if document contains relevant content
#     if 'patient' in text_lower or 'member' in text_lower:
#         if not any(f["field"] == "patient_name" for f in claim_fields):
#             claim_fields.insert(0, {"field": "patient_name", "label": "Patient Name", "type": "inputText", "fieldOrder": 0, "confidence": 0.70})
#         if not any(f["field"] == "member_id" for f in claim_fields):
#             claim_fields.append({"field": "member_id", "label": "Member ID", "type": "inputText", "fieldOrder": len(claim_fields) + 1, "confidence": 0.70})
    
#     if '$' in raw_text or 'amount' in text_lower:
#         if not any(f["field"] == "total_amount" for f in payment_fields):
#             payment_fields.append({"field": "total_amount", "label": "Total Amount", "type": "inputNumber", "fieldOrder": len(payment_fields) + 1, "confidence": 0.70})
#         if not any(f["field"] == "paid_amount" for f in payment_fields):
#             payment_fields.append({"field": "paid_amount", "label": "Paid Amount", "type": "inputNumber", "fieldOrder": len(payment_fields) + 1, "confidence": 0.70})
    
#     if 'claim' in text_lower:
#         if not any(f["field"] == "claim_number" for f in claim_fields):
#             claim_fields.append({"field": "claim_number", "label": "Claim Number", "type": "inputText", "fieldOrder": len(claim_fields) + 1, "confidence": 0.70})
    
#     if 'date' in text_lower or re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', raw_text):
#         if not any(f["field"] == "service_date" for f in service_line_fields):
#             service_line_fields.append({"field": "service_date", "label": "Service Date", "type": "inputDate", "fieldOrder": len(service_line_fields) + 1, "confidence": 0.70})
#         if not any(f["field"] == "payment_date" for f in payment_fields):
#             payment_fields.append({"field": "payment_date", "label": "Payment Date", "type": "inputDate", "fieldOrder": len(payment_fields) + 1, "confidence": 0.70})
    
#     # Re-number field orders
#     for i, f in enumerate(payment_fields, 1):
#         f["fieldOrder"] = i
#     for i, f in enumerate(claim_fields, 1):
#         f["fieldOrder"] = i
#     for i, f in enumerate(service_line_fields, 1):
#         f["fieldOrder"] = i
    
#     # Build sections array
#     sections = []
    
#     if payment_fields:
#         sections.append({
#             "sectionName": "File / Payment Information",
#             "sectionOrder": 1,
#             "fields": payment_fields[:15]  # Limit fields per section
#         })
    
#     if claim_fields:
#         sections.append({
#             "sectionName": "Claim Information",
#             "sectionOrder": 2,
#             "fields": claim_fields[:15]
#         })
    
#     if service_line_fields:
#         sections.append({
#             "sectionName": "Service Line Details",
#             "sectionOrder": 3,
#             "fields": service_line_fields[:15]
#         })
    
#     # Ensure at least one section exists
#     if not sections:
#         sections.append({
#             "sectionName": "Extracted Fields",
#             "sectionOrder": 1,
#             "fields": [{
#                 "field": "raw_data",
#                 "label": "Raw Data",
#                 "type": "inputText",
#                 "fieldOrder": 1,
#                 "confidence": 0.50
#             }]
#         })
    
#     total_fields = sum(len(s["fields"]) for s in sections)
#     logger.info(f"🔄 Fallback extracted {total_fields} fields across {len(sections)} sections")
#     return sections


# def extract_flat_keys_from_sections(dynamic_keys: Any) -> List[str]:
#     """
#     Extract flat field names from the sections structure.
#     Handles both new section-based format and legacy flat list format.
#     """
#     flat_keys = []
    
#     # If it's already a flat list of strings (legacy format)
#     if isinstance(dynamic_keys, list) and len(dynamic_keys) > 0:
#         if isinstance(dynamic_keys[0], str):
#             return dynamic_keys[:30]  # Already flat, return as-is
        
#         # New section-based format
#         for section in dynamic_keys:
#             if isinstance(section, dict) and "fields" in section:
#                 for field in section.get("fields", []):
#                     if isinstance(field, dict) and "field" in field:
#                         flat_keys.append(field["field"])
    
#     return flat_keys[:30]  # Limit to 30 keys


# def convert_text_to_dynamic_json(raw_text: str, dynamic_keys: Any, filename: str) -> Dict[str, Any]:
#     """
#     Use AI to convert text to JSON using only the dynamically identified keys.
#     Accepts both section-based (new) and flat list (legacy) formats for dynamic_keys.
#     """
#     # Extract flat keys from sections if needed
#     flat_keys = extract_flat_keys_from_sections(dynamic_keys)
    
#     if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
#         return convert_to_json_fallback(raw_text, flat_keys)
    
#     try:
#         # Clean text for AI processing
#         clean_text = raw_text.replace('\x00', '').replace('\r', '\n')
#         # Ensure text is properly encoded
#         clean_text = clean_text.encode('utf-8', errors='ignore').decode('utf-8')
        
#         client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
#         # Create dynamic JSON schema based on identified keys
#         schema_fields = []
#         for key in flat_keys[:20]:  # Limit to 20 keys for prompt size
#             schema_fields.append(f'"{key}": "extracted_value_or_null"')
        
#         schema_example = "{\n    " + ",\n    ".join(schema_fields) + "\n}"
        
#         prompt = f"""
#         Extract data from the following text and convert it to a structured JSON format.
        
#         Available keys found in text: {', '.join(flat_keys[:15])}
        
#         IMPORTANT: Return ONLY valid JSON without any markdown formatting or additional text.
        
#         Required JSON structure:
#         {{
#             "payer_info": {{
#                 "payer_name": "Insurance Company Name",
#                 "code": "PAYER123",
#                 "confidence": 90
#             }},
#             "payments": [
#                 {{
#                     "payment_reference": "actual_value_from_text_or_null",
#                     "payment_date": "YYYY-MM-DD_or_null", 
#                     "payment_amount": actual_number_or_0,
#                     "currency": "USD"
#                 }}
#             ],
#             "claims": [
#                 {{
#                     "claim_number": "actual_value_from_text_or_null",
#                     "patient_name": "actual_value_from_text_or_null",
#                     "member_id": "actual_value_from_text_or_null", 
#                     "provider_name": "actual_value_from_text_or_null",
#                     "total_billed_amount": actual_number_or_0,
#                     "total_allowed_amount": actual_number_or_0,
#                     "total_paid_amount": actual_number_or_0,
#                     "total_adjustment_amount": actual_number_or_0,
#                     "claim_status_code": "actual_value_from_text_or_null",
#                     "service_date_from": "YYYY-MM-DD_or_null",
#                     "service_date_to": "YYYY-MM-DD_or_null", 
#                     "validation_score": 85,
#                     "service_lines": [
#                         {{
#                             "line_number": 1,
#                             "cpt_code": "actual_value_from_text_or_null",
#                             "dos_from": "YYYY-MM-DD_or_null",
#                             "dos_to": "YYYY-MM-DD_or_null",
#                             "billed_amount": actual_number_or_0,
#                             "allowed_amount": actual_number_or_0, 
#                             "paid_amount": actual_number_or_0,
#                             "units": 1,
#                             "modifier1": "actual_value_from_text_or_null",
#                             "modifier2": "actual_value_from_text_or_null"
#                         }}
#                     ]
#                 }}
#             ],
#             "raw_key_value_pairs": {{
#                 "each_dynamic_key": "actual_extracted_value"
#             }},
#             "extraction_confidence": 85
#         }}
        
#         RULES:
#         1. Extract actual values from the text using the dynamic keys
#         2. Convert dates to YYYY-MM-DD format  
#         3. Convert amounts to numbers (no currency symbols)
#         4. Map dynamic keys to appropriate database fields
#         5. Create separate service lines for each service entry found
        
#         Text to extract from:
#         {clean_text[:4000]}
        
#         Return organized JSON structure:
#         """
        
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.7,
#             max_tokens=2000
#         )
        
#         content = response.choices[0].message.content.strip()
        
#         # Clean up response - handle multiple markdown formats
#         if content.startswith("```json"):
#             content = content[7:]
#         elif content.startswith("```"):
#             content = content[3:]
        
#         if content.endswith("```"):
#             content = content[:-3]
        
#         content = content.strip()
        
#         # Additional cleanup for common OpenAI formatting issues
#         if content.startswith('{') and not content.endswith('}'):
#             # Try to find the end of JSON
#             brace_count = 0
#             last_valid_pos = 0
#             for i, char in enumerate(content):
#                 if char == '{':
#                     brace_count += 1
#                 elif char == '}':
#                     brace_count -= 1
#                     if brace_count == 0:
#                         last_valid_pos = i + 1
#                         break
#             if last_valid_pos > 0:
#                 content = content[:last_valid_pos]
        
#         # Parse JSON with better error handling
#         try:
#             result = json.loads(content)
#         except json.JSONDecodeError as je:
#             logger.error(f"JSON decode error: {je}")
#             logger.error(f"Raw content: {content[:200]}...")
#             # Try to fix common JSON issues
#             content = content.replace('\\n', '\n').replace('\\"', '"')
#             # Remove trailing commas
#             content = re.sub(r',\s*}', '}', content)
#             content = re.sub(r',\s*]', ']', content)
#             result = json.loads(content)
        
#         # Post-process and enhance the result
#         result = enhance_json_result(result, flat_keys, raw_text)
        
#         # Ensure we have confidence score
#         if "extraction_confidence" not in result:
#             result["extraction_confidence"] = 75
        
#         logger.info(f"🤖 AI converted text to JSON with {len(result)} fields")
#         return result
        
#     except Exception as e:
#         logger.error(f"AI JSON conversion failed: {e}")
#         return convert_to_json_fallback(raw_text, flat_keys)

# def enhance_json_result(result: Dict[str, Any], dynamic_keys: List[str], raw_text: str) -> Dict[str, Any]:
#     """
#     Enhance the AI-generated JSON result by ensuring all dynamic keys are captured
#     and improving the structured data quality.
#     """
#     try:
#         # Ensure we have the required structure
#         if "raw_key_value_pairs" not in result:
#             result["raw_key_value_pairs"] = {}
#         if "claims" not in result:
#             result["claims"] = []
#         if "payments" not in result:
#             result["payments"] = []
        
#         # Extract key-value pairs if they're missing
#         raw_kvp = result.get("raw_key_value_pairs", {})
#         if len(raw_kvp) < len(dynamic_keys) * 0.5:  # If less than 50% of keys extracted
#             # Use fallback extraction for missing keys
#             fallback_data = convert_to_json_fallback(raw_text, dynamic_keys)
#             for key, value in fallback_data.items():
#                 if key not in raw_kvp and value and key != "extraction_confidence":
#                     raw_kvp[key] = value
#             result["raw_key_value_pairs"] = raw_kvp
        
#         # Enhance claims data if we have key-value pairs but sparse claim data
#         if raw_kvp and (not result["claims"] or len(result["claims"][0]) < 5):
#             enhanced_claim = create_enhanced_claim_from_kvp(raw_kvp)
#             if enhanced_claim:
#                 if not result["claims"]:
#                     result["claims"] = [enhanced_claim]
#                 else:
#                     # Merge with existing claim
#                     existing_claim = result["claims"][0]
#                     for key, value in enhanced_claim.items():
#                         if existing_claim.get(key) in [None, "null", "", "N/A"] and value not in [None, "null", "", "N/A"]:
#                             existing_claim[key] = value
        
#         # Enhance payments data similarly
#         if raw_kvp and not result["payments"]:
#             enhanced_payment = create_enhanced_payment_from_kvp(raw_kvp)
#             if enhanced_payment:
#                 result["payments"] = [enhanced_payment]
        
#         return result
        
#     except Exception as e:
#         logger.error(f"Error enhancing JSON result: {e}")
#         return result

# def create_enhanced_claim_from_kvp(kvp: Dict[str, Any]) -> Dict[str, Any]:
#     """Create an enhanced claim structure from key-value pairs."""
#     claim = {
#         "claim_number": None,
#         "patient_name": None,
#         "member_id": None,
#         "provider_name": None,
#         "total_billed_amount": 0.0,
#         "total_allowed_amount": 0.0,
#         "total_paid_amount": 0.0,
#         "total_adjustment_amount": 0.0,
#         "claim_status_code": None,
#         "service_date_from": None,
#         "service_date_to": None,
#         "validation_score": 80,
#         "service_lines": []
#     }
    
#     # Map common key patterns to claim fields
#     key_mappings = {
#         "patient_name": ["patient_name", "member_name", "name", "patient"],
#         "member_id": ["member_id", "patient_id", "id", "member_number"],
#         "claim_number": ["claim_number", "claim_id", "claim"],
#         "provider_name": ["provider_name", "provider", "doctor", "facility"],
#         "total_billed_amount": ["billed_amount", "claim_amount", "amount", "total_amount"],
#         "total_allowed_amount": ["allowed_amount", "approved_amount"],
#         "total_paid_amount": ["paid_amount", "payment_amount"],
#         "service_date_from": ["service_date", "date_of_service", "dos", "date"],
#         "service_date_to": ["service_date", "date_of_service", "dos", "date"]
#     }
    
#     for claim_field, possible_keys in key_mappings.items():
#         for key in possible_keys:
#             if key in kvp and kvp[key]:
#                 value = kvp[key]
#                 if claim_field in ["total_billed_amount", "total_allowed_amount", "total_paid_amount"]:
#                     try:
#                         # Extract numeric value
#                         if isinstance(value, str):
#                             value = re.sub(r'[^\d.]', '', value)
#                         claim[claim_field] = float(value) if value else 0.0
#                     except:
#                         claim[claim_field] = 0.0
#                 else:
#                     claim[claim_field] = str(value)
#                 break
    
#     # Create service line if we have service data
#     if any(claim[field] for field in ["service_date_from", "total_billed_amount"]):
#         service_line = {
#             "line_number": 1,
#             "cpt_code": kvp.get("cpt_code") or kvp.get("procedure_code") or "Unknown",
#             "dos_from": claim["service_date_from"],
#             "dos_to": claim["service_date_to"] or claim["service_date_from"],
#             "billed_amount": claim["total_billed_amount"],
#             "allowed_amount": claim["total_allowed_amount"],
#             "paid_amount": claim["total_paid_amount"],
#             "units": 1,
#             "modifier1": kvp.get("modifier1") or "None",
#             "modifier2": kvp.get("modifier2") or "None"
#         }
#         claim["service_lines"] = [service_line]
    
#     return claim if any(claim[field] for field in ["patient_name", "claim_number", "total_billed_amount"]) else None

# def create_enhanced_payment_from_kvp(kvp: Dict[str, Any]) -> Dict[str, Any]:
#     """Create an enhanced payment structure from key-value pairs."""
#     payment_keys = ["paid_amount", "payment_amount", "amount"]
#     payment_amount = 0.0
    
#     for key in payment_keys:
#         if key in kvp and kvp[key]:
#             try:
#                 value = kvp[key]
#                 if isinstance(value, str):
#                     value = re.sub(r'[^\d.]', '', value)
#                 payment_amount = float(value) if value else 0.0
#                 break
#             except:
#                 continue
    
#     if payment_amount > 0:
#         return {
#             "payment_reference": kvp.get("claim_number") or kvp.get("reference_number") or "Generated",
#             "payment_date": kvp.get("payment_date") or kvp.get("service_date") or kvp.get("date") or "2024-01-01",
#             "payment_amount": payment_amount,
#             "currency": "USD"
#         }
    
#     return None

# def convert_to_json_fallback(raw_text: str, dynamic_keys: List[str]) -> Dict[str, Any]:
#     """
#     Fallback method to convert text to JSON using pattern matching.
#     """
#     result = {"extraction_confidence": 50}
#     lines = raw_text.split('\n')
#     text_lower = raw_text.lower()

#     # Heuristic: Split text into claim blocks using a separator (e.g., 'claim number', 'claim id', etc.)
#     claim_start_patterns = [r'claim number', r'claim id', r'claim no', r'claim:']
#     claim_blocks = []
#     current_block = []
#     for line in lines:
#         if any(pat in line.lower() for pat in claim_start_patterns) and current_block:
#             claim_blocks.append(current_block)
#             current_block = [line]
#         else:
#             current_block.append(line)
#     if current_block:
#         claim_blocks.append(current_block)

#     claims = []
#     for block in claim_blocks:
#         claim_data = {}
#         for key in dynamic_keys:
#             value = None
#             key_patterns = [
#                 key.replace('_', ' '),
#                 key.replace('_', ''),
#                 key.upper(),
#                 key.title().replace('_', ' ')
#             ]
#             for line in block:
#                 line_lower = line.lower()
#                 for pattern in key_patterns:
#                     pattern_lower = pattern.lower()
#                     if pattern_lower in line_lower:
#                         parts = line.split(':', 1)
#                         if len(parts) == 2:
#                             value = parts[1].strip()
#                         else:
#                             for sep in ['=', '-', ' ']:
#                                 if sep in line:
#                                     parts = line.split(sep, 1)
#                                     if len(parts) == 2:
#                                         potential_value = parts[1].strip()
#                                         if len(potential_value) > 0 and len(potential_value) < 100:
#                                             value = potential_value
#                                         break
#                         if value:
#                             value = re.sub(r'[^\w\s\.\-\$,]', '', value)
#                             if len(value.strip()) > 0:
#                                 break
#                 if value:
#                     break
#             claim_data[key] = value
#         # Only add if at least one key has a value
#         if any(v for v in claim_data.values()):
#             claims.append(claim_data)

#     result['claims'] = claims if claims else []
#     logger.info(f"🔄 Fallback extracted {len(result['claims'])} claims from text")
#     return result