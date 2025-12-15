#!/usr/bin/env python3
"""
Diagnostic script to test JSON conversion issues
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from app.services.ai_template_processor import process_template_with_dynamic_extraction
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_json_conversion_issues():
    """Test different types of text to identify JSON conversion issues."""
    
    print("🔍 Diagnosing JSON Conversion Issues")
    print("=" * 50)
    
    # Test Case 1: Simple structured text
    test1_text = """
Patient Name: John Smith
Policy Number: POL123456
Claim Amount: $1,250.00
Date of Service: 2024-01-15
Provider Name: ABC Medical Center
Diagnosis Code: Z00.00
    """
    
    # Test Case 2: Medical/EOB-style text 
    test2_text = """
EXPLANATION OF BENEFITS
Member: Jane Doe
Member ID: 987654321
Claim Number: CLM-2024-001
Provider: XYZ Healthcare
Service Date: 03/15/2024
Billed Amount: $500.00
Allowed Amount: $400.00
Paid Amount: $320.00
Your Responsibility: $80.00
    """
    
    # Test Case 3: Text with special characters and formatting
    test3_text = """
Patient Information:
Name: María José García-Smith
ID#: 123-45-6789
DOB: 01/15/1985
Address: 123 Main St, Apt #2B
Phone: (555) 123-4567
Email: maria.garcia@email.com
    """
    
    test_cases = [
        ("Simple structured text", test1_text),
        ("EOB-style medical text", test2_text), 
        ("Text with special characters", test3_text)
    ]
    
    for i, (case_name, text) in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: {case_name}")
        print("-" * 30)
        
        try:
            # Process the text
            result = await process_template_with_dynamic_extraction(text, f"test_case_{i}.txt")
            
            # Check if we got valid JSON
            json_data = result.get("extraction_data", {})
            dynamic_keys = result.get("dynamic_keys", [])
            
            print(f"✅ Processing successful")
            print(f"   Dynamic keys found: {len(dynamic_keys)}")
            print(f"   Keys: {dynamic_keys[:5]}...")
            print(f"   JSON fields extracted: {len(json_data)}")
            
            # Check JSON structure
            if isinstance(json_data, dict):
                print(f"   ✅ Valid JSON structure")
                
                # Check for common fields
                common_fields = ['payments', 'claims', 'extraction_confidence']
                found_fields = [f for f in common_fields if f in json_data]
                print(f"   Expected structure fields: {found_fields}")
                
                # Show sample of extracted data
                print(f"   Sample data:")
                for key, value in list(json_data.items())[:3]:
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"     {key}: {value}")
                
            else:
                print(f"   ❌ Invalid JSON structure: {type(json_data)}")
                
        except json.JSONDecodeError as je:
            print(f"   ❌ JSON Parse Error: {je}")
            print(f"   Raw response type: {type(result.get('extraction_data', 'N/A'))}")
            
        except Exception as e:
            print(f"   ❌ Processing Error: {e}")
            import traceback
            traceback.print_exc()

async def test_openai_availability():
    """Test if OpenAI is properly configured."""
    
    print("\n🤖 Testing OpenAI Configuration")
    print("-" * 30)
    
    try:
        from app.services.ai_template_processor import OPENAI_AVAILABLE, OPENAI_API_KEY
        
        print(f"OpenAI Available: {'✅ YES' if OPENAI_AVAILABLE else '❌ NO'}")
        print(f"API Key Present: {'✅ YES' if OPENAI_API_KEY else '❌ NO'}")
        
        if OPENAI_API_KEY:
            print(f"API Key Length: {len(OPENAI_API_KEY)} characters")
            print(f"API Key Preview: {OPENAI_API_KEY[:8]}...")
        
        if OPENAI_AVAILABLE:
            # Test a simple OpenAI call
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Return just the word 'test' in JSON format: {\"result\": \"test\"}"}],
                temperature=0.1,
                max_tokens=50
            )
            
            content = response.choices[0].message.content.strip()
            print(f"✅ OpenAI Test Response: {content}")
            
            # Test JSON parsing
            try:
                test_json = json.loads(content)
                print(f"✅ JSON parsing successful: {test_json}")
            except:
                print(f"❌ JSON parsing failed for: {content}")
        
    except Exception as e:
        print(f"❌ OpenAI Test Error: {e}")

async def main():
    print("🚀 Starting JSON Conversion Diagnostics")
    print("=" * 60)
    
    # Test OpenAI first
    await test_openai_availability()
    
    # Test JSON conversion
    await test_json_conversion_issues()
    
    print("\n" + "=" * 60)
    print("🎯 Diagnostic Complete!")
    print("\nIf you see specific errors above, please share them")
    print("so I can provide targeted fixes for the JSON conversion issues.")

if __name__ == "__main__":
    asyncio.run(main())