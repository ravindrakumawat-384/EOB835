"""
AI-Powered 835 EDI Format Generator
Uses OpenAI to intelligently analyze claim data and generate proper 835 format
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime
import openai
from dotenv import load_dotenv
from ..utils.logger import get_logger
logger = get_logger(__name__)
# Load environment variables
load_dotenv()

# Initialize OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_AVAILABLE = bool(OPENAI_API_KEY)

if OPENAI_AVAILABLE:
    openai.api_key = OPENAI_API_KEY

class AI835Generator:
    """AI-powered 835 EDI format generator"""
    
    def __init__(self):
        self.model = "gpt-4"  # Use GPT-4 for better accuracy
        
    def generate_intelligent_835(self, claim_data: Dict[str, Any]) -> str:
        """
        Generate 835 EDI format using AI model for intelligent analysis
        """
        if not OPENAI_AVAILABLE:
            # Fallback to standard generation if AI not available
            return self._generate_standard_835(claim_data)
            
        try:
            # Prepare claim data for AI analysis
            claim_json = json.dumps(claim_data, indent=2, default=str)
            
            # Create AI prompt for 835 generation
            prompt = self._create_835_generation_prompt(claim_json)
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert healthcare EDI specialist who generates perfect 835 Electronic Remittance Advice (ERA) files. You understand all EDI transaction codes, segment requirements, and healthcare billing standards."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.1  # Low temperature for consistent output
            )
            
            # Extract the generated 835 content
            ai_generated_835 = response.choices[0].message.content.strip()
            
            # Validate and clean the AI response
            validated_835 = self._validate_and_clean_835(ai_generated_835)
            
            logger.info("🤖 AI Generated 835 format successfully")
            return validated_835
            
        except Exception as e:
            logger.error(f"❌ AI 835 generation failed: {e}")
            return self._generate_standard_835(claim_data)
    
    def _create_835_generation_prompt(self, claim_json: str) -> str:
        """Create a detailed prompt for AI 835 generation"""
        
        current_date = datetime.now()
        
        prompt = f"""
Generate a complete 835 Electronic Remittance Advice (ERA) in proper EDI format based on the following claim data:

CLAIM DATA:
{claim_json}

REQUIREMENTS:
1. Generate proper EDI 835 segments in correct sequence
2. Use proper EDI delimiters: * for elements, ~ for segment terminator
3. Include all required segments: ISA, GS, ST, BPR, TRN, CUR, REF, DTM, N1 loops, LX, CLP, NM1, SVC, SE, GE, IEA
4. Use realistic but compliant data where claim data is missing
5. Format dates as YYYYMMDD, amounts with 2 decimal places
6. Use today's date: {current_date.strftime('%Y%m%d')} for current date references
7. Generate proper interchange control numbers and reference numbers

SPECIFIC FIELD MAPPINGS:
- Use claim_number for CLP segment patient control number
- Use patient_name for NM1*QC segment (format: Last*First*Middle)
- Use payer_name for N1*PR segment 
- Use payment_reference for BPR and TRN segments
- Use payment_amount and total_billed_amount for financial segments
- Generate appropriate CPT codes for service lines if missing

EDI 835 SEGMENT STRUCTURE:
ISA - Interchange Control Header
GS - Functional Group Header  
ST - Transaction Set Header
BPR - Beginning Segment for Payment Order/Remittance
TRN - Reassociation Trace Number
CUR - Currency
REF - Reference Information
DTM - Date/Time Reference
N1 - Entity Name (Payer)
N3 - Address Information
N4 - Geographic Location
N1 - Entity Name (Payee)
N3 - Address Information  
N4 - Geographic Location
LX - Header Number
CLP - Claim Payment Information
NM1 - Patient Name
DTM - Statement Date
SVC - Service Payment Information (for each service)
DTM - Service Date
SE - Transaction Set Trailer
GE - Functional Group Trailer
IEA - Interchange Control Trailer

Generate ONLY the EDI 835 format content with proper segments and delimiters. Do not include explanations or additional text.
"""
        return prompt
    
    def _validate_and_clean_835(self, ai_response: str) -> str:
        """Validate and clean AI-generated 835 content"""
        
        # Remove any markdown code blocks or extra formatting
        cleaned = ai_response.replace("```", "").replace("`", "")
        
        # Split into lines and process
        lines = cleaned.split('\n')
        edi_segments = []
        
        for line in lines:
            line = line.strip()
            if line and ('*' in line or '~' in line):
                # This looks like an EDI segment
                if not line.endswith('~'):
                    line += '~'
                edi_segments.append(line)
        
        # Join segments with newlines for readability
        final_835 = '\n'.join(edi_segments)
        
        # Basic validation - ensure key segments are present
        required_segments = ['ISA*', 'GS*', 'ST*835*', 'BPR*', 'SE*', 'GE*', 'IEA*']
        for segment in required_segments:
            if segment not in final_835:
                logger.warning(f"Missing required segment in AI 835: {segment}")
        return final_835
    
    def _generate_standard_835(self, claim_data: Dict[str, Any]) -> str:
        """Fallback standard 835 generation when AI is not available"""
        
        # Extract key data
        claim_number = str(claim_data.get('claim_number', 'UNKNOWN'))
        patient_name = str(claim_data.get('patient_name', 'UNKNOWN, PATIENT'))
        payer_name = str(claim_data.get('payer_name', 'UNKNOWN PAYER'))
        payment_ref = str(claim_data.get('payment_reference', 'AUTO-REF'))
        total_billed = float(claim_data.get('total_billed_amount', 0))
        total_paid = float(claim_data.get('total_paid_amount') or claim_data.get('payment_amount', 0))
        
        # Current timestamp
        now = datetime.now()
        current_date = now.strftime('%Y%m%d')
        current_time = now.strftime('%H%M')
        interchange_control = f"{now.strftime('%y%m%d%H%M%S')}"[:9].ljust(9, '0')
        
        # Format patient name
        if ',' in patient_name:
            parts = patient_name.split(',', 1)
            patient_last = parts[0].strip()
            patient_first = parts[1].strip() if len(parts) > 1 else ''
        else:
            name_parts = patient_name.split()
            patient_first = name_parts[0] if name_parts else 'UNKNOWN'
            patient_last = name_parts[-1] if len(name_parts) > 1 else 'PATIENT'
        
        # Generate standard 835 format
        segments = [
            f"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *{now.strftime('%y%m%d')}*{current_time}*^*00501*{interchange_control}*0*P*:~",
            f"GS*HP*SENDER*RECEIVER*{current_date}*{current_time}*1*X*005010X221A1~",
            "ST*835*0001*005010X221A1~",
            f"BPR*I*{total_paid:.2f}*C*ACH*CCP*01*{payment_ref}*DA*123456789*1234567890*{current_date}*01*123456789*DA*123456789~",
            f"TRN*1*{payment_ref}*1234567890~",
            "CUR*85*USD~",
            f"REF*EV*{payment_ref}~",
            f"DTM*405*{current_date}~",
            f"N1*PR*{payer_name}~",
            "N3*P.O. BOX 31362~",
            "N4*SALT LAKE CITY*UT*84131~",
            "N1*PE*NEXGEN HEALTHCARE LLC*XX*1234567890~",
            "N3*21 WATERVILLE RD~",
            "N4*AVON*CT*06001~",
            "LX*1~",
            f"CLP*{claim_number}*1*{total_billed:.2f}*{total_paid:.2f}*0.00*MC*{payment_ref}*11*1~",
            f"NM1*QC*1*{patient_last}*{patient_first}***MI*{claim_number}~",
            f"DTM*232*{current_date}~",
            f"SVC*HC:99213*{total_billed:.2f}*{total_paid:.2f}**1~",
            f"DTM*472*{current_date}~",
            "SE*19*0001~",
            "GE*1*1~",
            f"IEA*1*{interchange_control}~"
        ]
        
        return '\n'.join(segments)

    def enhance_service_lines_with_ai(self, claim_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use AI to enhance service line data with appropriate CPT codes and descriptions"""
        
        if not OPENAI_AVAILABLE:
            return self._generate_default_service_lines(claim_data)
            
        try:
            # Create prompt for service line enhancement
            prompt = self._create_service_line_prompt(claim_data)
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Use GPT-3.5 for faster response
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical coding expert who assigns accurate CPT codes and service descriptions based on claim information."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.2
            )
            
            # Parse AI response to extract service lines
            ai_response = response.choices[0].message.content.strip()
            enhanced_lines = self._parse_ai_service_lines(ai_response)
            
            logger.info(f"🤖 AI enhanced {len(enhanced_lines)} service lines")
            return enhanced_lines
            
        except Exception as e:
            logger.error(f"❌ AI service line enhancement failed: {e}")
            return self._generate_default_service_lines(claim_data)
    
    def _create_service_line_prompt(self, claim_data: Dict[str, Any]) -> str:
        """Create prompt for AI service line enhancement"""
        
        claim_json = json.dumps(claim_data, indent=2, default=str)
        
        prompt = f"""
Based on the following claim data, suggest appropriate CPT codes and service descriptions:

CLAIM DATA:
{claim_json}

Generate 1-3 realistic service lines in JSON format with:
- cpt_code: Valid CPT procedure code
- description: Service description
- billed_amount: Reasonable amount
- paid_amount: Payment amount
- units: Number of units (usually 1)
- dos_from: Service date

Return ONLY valid JSON array format like:
[
  {{
    "cpt_code": "99213",
    "description": "Office Visit Level 3",
    "billed_amount": 150.00,
    "paid_amount": 120.00,
    "units": 1,
    "dos_from": "2025-12-07"
  }}
]
"""
        return prompt
    
    def _parse_ai_service_lines(self, ai_response: str) -> List[Dict[str, Any]]:
        """Parse AI response to extract service lines"""
        
        try:
            # Try to extract JSON from the response
            if '[' in ai_response and ']' in ai_response:
                start = ai_response.find('[')
                end = ai_response.rfind(']') + 1
                json_str = ai_response[start:end]
                service_lines = json.loads(json_str)
                return service_lines
        except:
            pass
        
        # Fallback to default if parsing fails
        return self._generate_default_service_lines({})
    
    def _generate_default_service_lines(self, claim_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate default service lines when AI is not available"""
        
        total_billed = float(claim_data.get('total_billed_amount', 150.00))
        total_paid = float(claim_data.get('total_paid_amount') or claim_data.get('payment_amount', 120.00))
        service_date = claim_data.get('service_date_from', datetime.now().strftime('%Y-%m-%d'))
        
        return [{
            'cpt_code': '99213',
            'description': 'Office Visit Level 3',
            'billed_amount': total_billed if total_billed > 0 else 150.00,
            'paid_amount': total_paid if total_paid > 0 else 120.00,
            'units': 1,
            'dos_from': service_date
        }]

# Global instance
ai_835_generator = AI835Generator()