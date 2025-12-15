#!/usr/bin/env python3
"""
Test script to demonstrate the dynamic template processing API.
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.ai_template_processor import (
    extract_dynamic_keys_from_text,
    convert_text_to_dynamic_json
)

def test_dynamic_key_extraction():
    """Test the dynamic key extraction with sample text."""
    
    # Sample text that might come from different types of documents
    sample_texts = [
        # EOB Document
        """
        EXPLANATION OF BENEFITS
        Patient Name: John Smith
        Member ID: 12345678
        Policy Number: ABC-123-DEF
        Service Date: 10/15/2025
        Provider: City Medical Center
        Total Billed Amount: $250.00
        Insurance Paid: $200.00
        Patient Responsibility: $50.00
        Claim Number: CLM789456
        Authorization Code: AUTH123
        """,
        
        # Invoice Document
        """
        INVOICE #INV-2025-001
        Bill To: ABC Company
        Address: 123 Main St, Anytown, ST 12345
        Invoice Date: December 8, 2025
        Due Date: January 7, 2026
        
        Description: Consulting Services
        Quantity: 40 hours
        Rate: $75.00/hour
        Subtotal: $3,000.00
        Tax Rate: 8.5%
        Tax Amount: $255.00
        Total Amount: $3,255.00
        """,
        
        # Medical Report
        """
        PATIENT MEDICAL REPORT
        Patient: Jane Doe
        DOB: 03/15/1980
        MRN: MR123456
        Visit Date: 12/08/2025
        Physician: Dr. Sarah Johnson
        Department: Cardiology
        
        Chief Complaint: Chest pain
        Diagnosis: Hypertension
        Procedure Code: 99213
        Treatment Plan: Medication adjustment
        Next Appointment: 01/15/2026
        """
    ]
    
    for i, sample_text in enumerate(sample_texts, 1):
        print(f"\n{'='*60}")
        print(f"🧪 TEST {i}: PROCESSING SAMPLE DOCUMENT")
        print('='*60)
        
        print(f"📄 Original Text (first 200 chars):")
        print(f"{sample_text[:200]}...")
        
        # Step 1: Extract dynamic keys
        print(f"\n🔑 STEP 1: EXTRACTING DYNAMIC KEYS")
        dynamic_keys = extract_dynamic_keys_from_text(sample_text)
        print(f"Found {len(dynamic_keys)} dynamic keys:")
        for j, key in enumerate(dynamic_keys, 1):
            print(f"   {j}. {key}")
        
        # Step 2: Convert to JSON using dynamic keys
        print(f"\n🤖 STEP 2: CONVERTING TO JSON WITH DYNAMIC KEYS")
        json_result = convert_text_to_dynamic_json(sample_text, dynamic_keys, f"test_document_{i}.txt")
        
        print(f"Generated JSON:")
        print(json.dumps(json_result, indent=2))
        
        # Analyze the results
        extracted_fields = [k for k, v in json_result.items() if v is not None and k != 'extraction_confidence']
        print(f"\n📊 RESULTS ANALYSIS:")
        print(f"   - Dynamic keys identified: {len(dynamic_keys)}")
        print(f"   - Fields with extracted values: {len(extracted_fields)}")
        print(f"   - Extraction confidence: {json_result.get('extraction_confidence', 'N/A')}%")
        print(f"   - Success rate: {len(extracted_fields)}/{len(dynamic_keys)} = {len(extracted_fields)/len(dynamic_keys)*100:.1f}%")

def test_api_simulation():
    """Simulate the complete API workflow."""
    print(f"\n{'='*60}")
    print(f"🚀 API WORKFLOW SIMULATION")
    print('='*60)
    
    # Simulate file upload with sample content
    sample_filename = "patient_report.txt"
    sample_content = """
    PATIENT CARE SUMMARY
    Patient Name: Robert Johnson
    Account Number: ACC-789123
    Visit Date: December 8, 2025
    Admission Time: 09:30 AM
    Discharge Time: 02:15 PM
    
    Primary Physician: Dr. Michael Chen
    Specialty: Internal Medicine
    Room Number: 205-B
    
    Diagnosis Codes:
    - Primary: J44.1 (COPD with exacerbation)
    - Secondary: I10 (Hypertension)
    
    Procedures:
    - Chest X-ray: $150.00
    - Blood work panel: $75.00
    - Consultation fee: $200.00
    
    Insurance Information:
    - Primary Insurance: Blue Cross Blue Shield
    - Policy ID: BCBS-456789
    - Group Number: GRP-001
    
    Total Charges: $425.00
    Insurance Coverage: $340.00
    Patient Copay: $85.00
    
    Follow-up Required: Yes
    Next Appointment: January 15, 2026
    """
    
    print(f"📁 Simulating file upload: {sample_filename}")
    print(f"📄 Content length: {len(sample_content)} characters")
    
    # Step 1: Extract dynamic keys (simulating AI analysis)
    print(f"\n🔍 STEP 1: DYNAMIC KEY EXTRACTION")
    dynamic_keys = extract_dynamic_keys_from_text(sample_content)
    print(f"✅ Extracted {len(dynamic_keys)} dynamic keys")
    
    # Step 2: Convert to structured JSON
    print(f"\n🤖 STEP 2: AI TEXT-TO-JSON CONVERSION")
    json_result = convert_text_to_dynamic_json(sample_content, dynamic_keys, sample_filename)
    
    # Step 3: Simulate database save (would happen in real API)
    print(f"\n💾 STEP 3: DATABASE STORAGE SIMULATION")
    template_id = "template-123e4567-e89b-12d3-a456-426614174000"
    
    api_response = {
        "template_id": template_id,
        "filename": sample_filename,
        "text_record_id": "text-record-123",
        "json_record_id": "json-record-456", 
        "raw_text_length": len(sample_content),
        "dynamic_keys_found": len(dynamic_keys),
        "dynamic_keys": dynamic_keys,
        "json_data": json_result,
        "message": "Template processed successfully"
    }
    
    print(f"📋 API Response:")
    print(json.dumps(api_response, indent=2))
    
    return api_response

if __name__ == "__main__":
    print("🔬 DYNAMIC TEMPLATE PROCESSING TEST")
    print("="*60)
    
    try:
        # Test dynamic key extraction with different document types
        test_dynamic_key_extraction()
        
        # Test complete API workflow simulation
        api_result = test_api_simulation()
        
        print(f"\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print(f"✅ Dynamic key extraction working")
        print(f"✅ AI text-to-JSON conversion working") 
        print(f"✅ API workflow simulation complete")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()