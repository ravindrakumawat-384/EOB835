"""
Test script to verify file validation functionality.
"""

import sys
sys.path.append('/home/ditsdev370/Project/EOB835')

from app.services.file_content_validator import (
    validate_extracted_text,
    validate_ai_extraction_result,
    validate_json_conversion,
    comprehensive_file_validation
)

def test_text_validation():
    print("Testing text validation...")
    
    # Test valid text
    valid_text = """
    CheckSummary TransactionDate:October15,2025
    REGENCEBLUESHIELD PayeeTaxID: 991989129 PayeeName: EXCELLEDHEALINGLLC
    POBOX1106 PayeeID: 1013742964 PayeeAddress: 7202MERORD
    LEWISTON,ID83501 Check/EFTTraceNumber: 0197965047 
    PaymentAmount: $395.87
    Check/EFTDate: 10/15/2025
    PatientName:KELLNERJR,CHARLESR ClaimNumber:E71270615700 ClaimDate:09/01/2025-09/01/2025
    """
    
    is_valid, error = validate_extracted_text(valid_text, "test.pdf")
    print(f"Valid text result: {is_valid}, error: {error}")
    
    # Test invalid text (too short)
    invalid_text = "short"
    is_valid, error = validate_extracted_text(invalid_text, "test.pdf")
    print(f"Invalid text result: {is_valid}, error: {error}")
    
    # Test empty text
    empty_text = ""
    is_valid, error = validate_extracted_text(empty_text, "test.pdf")
    print(f"Empty text result: {is_valid}, error: {error}")

def test_ai_validation():
    print("\nTesting AI validation...")
    
    # Test valid AI result
    valid_ai_result = {
        "confidence": 85,
        "payer_info": {
            "name": "RegenceBlueShield",
            "code": "REGENCE",
            "confidence": 90
        },
        "payment": {
            "payment_reference": "0197965047",
            "payment_date": "2025-10-15",
            "payment_amount": 395.87,
            "currency": "USD",
            "confidence": 95
        },
        "claims": [
            {
                "claim_number": "E71270615700",
                "patient_name": "KELLNERJR,CHARLESR",
                "member_id": "123456",
                "total_paid_amount": 100.0,
                "confidence": 80
            }
        ]
    }
    
    is_valid, error = validate_ai_extraction_result(valid_ai_result, "test.pdf")
    print(f"Valid AI result: {is_valid}, error: {error}")
    
    # Test invalid AI result (low confidence)
    invalid_ai_result = {
        "confidence": 10,
        "payer_info": {"name": "Unknown Payer"},
        "payment": {"payment_amount": 0},
        "claims": []
    }
    
    is_valid, error = validate_ai_extraction_result(invalid_ai_result, "test.pdf")
    print(f"Invalid AI result: {is_valid}, error: {error}")

def test_comprehensive_validation():
    print("\nTesting comprehensive validation...")
    
    valid_text = """
    CheckSummary TransactionDate:October15,2025
    REGENCEBLUESHIELD PayeeTaxID: 991989129 PayeeName: EXCELLEDHEALINGLLC
    PaymentAmount: $395.87 ClaimNumber:E71270615700 PatientName:KELLNERJR,CHARLESR
    """
    
    valid_ai_result = {
        "confidence": 85,
        "payer_info": {"name": "RegenceBlueShield", "code": "REGENCE"},
        "payment": {"payment_amount": 395.87},
        "claims": [{"claim_number": "E71270615700", "patient_name": "KELLNERJR,CHARLESR"}]
    }
    
    is_valid, error = comprehensive_file_validation(valid_text, valid_ai_result, "test.pdf")
    print(f"Comprehensive validation result: {is_valid}, error: {error}")

if __name__ == "__main__":
    test_text_validation()
    test_ai_validation()
    test_comprehensive_validation()