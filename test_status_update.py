#!/usr/bin/env python3
"""
Test script to verify that file status updates work correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.pg_upload_files import update_file_status
from app.services.file_content_validator import (
    validate_extracted_text, 
    validate_ai_extraction_result,
    comprehensive_file_validation
)

def test_status_update():
    """Test updating file status to unreadable."""
    print("🧪 Testing file status update...")
    
    # Test with a fake file ID (you can replace with a real one from your database)
    test_file_id = "test123"
    
    # Test updating status to unreadable
    result = update_file_status(test_file_id, "unreadable", "Test: File content is unreadable")
    print(f"✅ Status update result: {result}")
    
    return result

def test_text_validation():
    """Test text validation functions."""
    print("\n🧪 Testing text validation...")
    
    # Test with empty/invalid text
    invalid_texts = [
        "",
        "abc",  # Too short
        "!!!@@@###$$$%%%",  # Mostly non-printable patterns
        "Random text without any medical or insurance content"
    ]
    
    for i, text in enumerate(invalid_texts):
        is_valid, error = validate_extracted_text(text, f"test_file_{i}.pdf")
        print(f"Text {i+1}: Valid={is_valid}, Error='{error}'")
    
    # Test with valid-looking text
    valid_text = """
    REGENCE BLUE SHIELD PayeeTaxID: 991989129 PayeeName: EXCELLED HEALING LLC
    Check Date: 10/15/2025 Payment Amount: $395.87
    Patient Name: KELLNER JR, CHARLES R Claim Number: E71270615700 
    Claim Date: 09/01/2025-09/01/2025 Claim Status Code: 2
    """
    
    is_valid, error = validate_extracted_text(valid_text, "valid_file.pdf")
    print(f"Valid text: Valid={is_valid}, Error='{error}'")

def test_ai_validation():
    """Test AI extraction result validation."""
    print("\n🧪 Testing AI extraction validation...")
    
    # Test with low confidence result
    low_confidence_result = {
        "confidence": 25,  # Below threshold
        "payer_info": {"name": "Unknown Payer"},
        "payment": {"payment_amount": 0},
        "claims": []
    }
    
    is_valid, error = validate_ai_extraction_result(low_confidence_result, "test_file.pdf")
    print(f"Low confidence result: Valid={is_valid}, Error='{error}'")
    
    # Test with good result
    good_result = {
        "confidence": 85,
        "payer_info": {"name": "Regence Blue Shield"},
        "payment": {"payment_amount": 395.87},
        "claims": [{"claim_number": "E71270615700"}]
    }
    
    is_valid, error = validate_ai_extraction_result(good_result, "test_file.pdf")
    print(f"Good result: Valid={is_valid}, Error='{error}'")

if __name__ == "__main__":
    print("🔬 Running file status and validation tests...\n")
    
    try:
        # Test status update
        test_status_update()
        
        # Test validation functions
        test_text_validation()
        test_ai_validation()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()