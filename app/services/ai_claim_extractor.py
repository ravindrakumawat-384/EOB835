from typing import List, Dict, Any
import uuid
import json
import os
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

def ai_extract_claims(raw_text: str, dynamic_key: List[str]) -> Dict[str, Any]:
    """
    Use ONLY AI model to extract claims from raw text and convert to structured JSON.
    Returns extraction result with confidence scores.
    """
    if not raw_text or raw_text.strip() == "":
        return {"claims": [], "confidence": 0, "error": "No text to process"}
    
    # Use ONLY AI extraction - provide fallback for testing
    if OPENAI_AVAILABLE and OPENAI_API_KEY:
        try:
            result = extract_with_openai(raw_text, dynamic_key)
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



def extract_with_openai(raw_text: str, dynamic_keys: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract structured data from raw text using dynamic_keys driven schema.
    """

    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        prompt = """
            You are given TWO inputs.

            INPUT 1:
            A JSON object named `dynamic_keys`.
            It defines the EXACT response schema.
            It contains sections and fields with metadata.

            INPUT 2:
            Raw document text.

            GOAL:
            Return extracted data by COPYING the structure of `dynamic_keys`
            and ADDING ONE key named `value` inside EACH field.

            STRICT RULES:

            1. DO NOT remove any existing keys.
            2. DO NOT rename any keys.
            3. DO NOT add new keys except `value`.
            4. DO NOT reorder sections or fields.
            5. Preserve ALL field properties:
            - id
            - field
            - label
            - type
            - fieldOrder
            - confidence
            6. Add `"value"` to every field.
            7. Extract values ONLY from text.
            8. If value is not found, set `"value": null`.

            LEVEL BEHAVIOR:
            - dynamic_keys = schema
            - section = grouping
            - field = extraction unit

            MANDATORY OUTPUT FORMAT:

            {
            "sections": [
                {
                "id": "<same as input>",
                "sectionName": "<same as input>",
                "dataKey": "<same as input>",
                "sectionOrder": <same as input>,
                "fields": [
                    {
                    "id": "<same>",
                    "field": "<same>",
                    "label": "<same>",
                    "type": "<same>",
                    "fieldOrder": <same>,
                    "confidence": <same>,
                    "value": "<extracted_value_or_null>"
                    }
                ]
                }
            ]
            }

            NO explanations.
            NO markdown.
            ONLY valid JSON.

            dynamic_keys:
            """ + json.dumps(dynamic_keys, ensure_ascii=False) + """

            RAW TEXT:
            """ + raw_text[:4000]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a strict JSON extraction engine."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=3000,
        )

        content = response.choices[0].message.content.strip()

        # Remove markdown if present
        if content.startswith("```"):
            content = content.split("```")[1]

        result = json.loads(content)

        # HARD GUARANTEE: every field has `value`
        for section in result.get("sections", []):
            for field in section.get("fields", []):
                field.setdefault("value", None)
        print("OpenAI extraction result:=========", result)
        return result

    except json.JSONDecodeError as e:
        logger.error("JSON decode failed", exc_info=True)
        return {
            "sections": [],
            "error": "Invalid JSON returned by AI",
            "details": str(e),
        }

    except openai.OpenAIError as e:
        logger.error("OpenAI API error", exc_info=True)
        return {
            "sections": [],
            "error": "OpenAI API error",
            "details": str(e),
        }

    except Exception as e:
        logger.error("Unexpected extraction error", exc_info=True)
        return {
            "sections": [],
            "error": "Unhandled extraction error",
            "details": str(e),
        }


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

    # iterate all sections → all fields
    for section in data.get("sections", []):
        for field in section.get("fields", []):

            field_name = field.get("field")
            value = field.get("value")
            confidence = field.get("confidence")

            print("field_name===========:", field_name)

            if field_name == "payer":
                result["payer_name"] = value

            elif field_name == "remark_payer_code":
                result["payer_code"] = value

            elif field_name == "check_eft_trace_number":
                result["payment_reference"] = value

            elif field_name == "check_eft_date":
                result["payment_date"] = value

            elif field_name == "payment_amount":
                result["payment_amount"] = float(value) if value is not None and value != '' else 0.0

            elif field_name == "claim_payment":
                result["claim_payment"] = value

            elif field_name == "claim_number":
                result["claim_number"] = value
            
            elif field_name == "patient_name":
                result["patient_name"] = value
            
            elif field_name == "payee_name":
                result["payee_name"] = value

            elif field_name == "payment":
                # print( "value payment:", value)
                # print( "type payment:", type(value))
                # print( "s1:", int(float(value)))
                # print( "s2:", str(int(float(value))))
                result["payment"] = int(float(value)) if value is not None and value != '' else 0



            elif field_name == "claim_payment":
                result["claim_payment"] = int(float(value)) if value is not None and value != '' else 0
            
            elif field_name == "total_paid":
                result["total_paid"] = int(float(value)) if value is not None and value != '' else 0

            elif field_name == "adj_amount":
                result["adj_amount"] = int(float(value)) if value is not None and value != '' else 0

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
                result["units"] = value
                
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
    
    # for section in extracted.get("sections"):
    #     key = section.get("file_payment_information")
    #     print( "key:", key)


    # payment_info_fields = extracted["sections"][0]["fields"]
    # claim_info_fields = extracted["sections"][1]["fields"]
    # serviceline_info_fields = extracted["sections"][2]["fields"]

    # for i in payment_info_fields:
    #     print( "payment_info_field:", i)

    # for i in claim_info_fields:
    #     print( "claim_info_field:", i)

    # for i in serviceline_info_fields:
    #     print( "serviceline_info_field:", i)

    # payer_info = extracted.get("fields", {})
    # payment_info = extracted.get("payment", {})
    # overall_confidence = extracted.get("confidence", 0)
    
    # for claim in extracted.get("claims", []):
    #     flat_claim = {
    #         "payer_name": payer_info.get("name", "Unknown Payer"),
    #         "payer_code": payer_info.get("code"),
    #         "payment_reference": payment_info.get("payment_reference"),
    #         "payment_date": payment_info.get("payment_date"),
    #         "payment_amount": payment_info.get("payment_amount", 0),
    #         "overall_confidence": overall_confidence,
    #         "payer_confidence": payer_info.get("confidence", 0),
    #         "claim_confidence": claim.get("confidence", 0),
    #         **claim
    #     }
    #     flat.append(flat_claim)

    # flat = extract_payment_fields(extracted)

    
    return flat
