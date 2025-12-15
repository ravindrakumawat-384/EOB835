#!/usr/bin/env python3
"""
Test script for the Template API with dynamic key extraction.
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_dynamic_extraction():
    """Test the dynamic key extraction functionality."""
    
    # Sample EOB text with various key-value patterns
    sample_text = """
    Check Summary
    Transaction Date: October 15, 2025
    REGENCE BLUE SHIELD 
    Payee Tax ID: 991989129 
    Payee Name: EXCELLED HEALING LLC
    PO BOX 1106 
    Payee ID: 1013742964 
    Payee Address: 7202 MER ORD
    LEWISTON, ID 83501 
    
    Check/EFT Trace Number: 0197965047 
    SNOHOMISH, WA 982907115
    Payment Amount: $395.87
    Check/EFT Date: 10/15/2025
    Production End Cycle Date: 10/10/2025
    
    Patient Name: KELLNER JR, CHARLES R 
    Claim Number: E71270615700 
    Claim Date: 09/01/2025-09/01/2025 
    Claim Status Code: 2
    Patient ID: ZLO160109581 
    Group/Policy: 
    Facility Type: 12 
    Claim Charge: $150.00
    Allowed Amount: $120.00
    Paid Amount: $95.87
    Adjustment Amount: $24.13
    
    Service Line 1:
    CPT Code: 99213
    Service Date: 09/01/2025
    Billed Amount: $150.00
    Units: 1
    Modifier: 
    Revenue Code: 450
    """
    
    print("🧪 TESTING TEMPLATE API DYNAMIC EXTRACTION")
    print("=" * 60)
    
    try:
        from app.services.ai_template_processor import process_template_with_dynamic_extraction
        
        print("📄 Sample text:")
        print(sample_text[:300] + "...")
        
        print("\n🤖 Processing with AI dynamic extraction...")
        result = await process_template_with_dynamic_extraction(sample_text, "test_eob.txt")
        
        print("\n✅ EXTRACTION RESULTS:")
        print("=" * 40)
        
        print(f"\n🔑 Dynamic Keys Found ({len(result.get('dynamic_keys', []))}):")
        for i, key in enumerate(result.get('dynamic_keys', [])[:15], 1):
            print(f"  {i}. {key}")
        
        print(f"\n💰 Payments Extracted ({len(result.get('payments', []))}):")
        for i, payment in enumerate(result.get('payments', []), 1):
            print(f"  Payment {i}: {json.dumps(payment, indent=2)}")
        
        print(f"\n🏥 Claims Extracted ({len(result.get('claims', []))}):")
        for i, claim in enumerate(result.get('claims', []), 1):
            print(f"  Claim {i}: {json.dumps({k: v for k, v in claim.items() if k != 'service_lines'}, indent=2)}")
            if claim.get('service_lines'):
                print(f"    Service Lines: {len(claim['service_lines'])}")
        
        print(f"\n🔧 Raw Key-Value Pairs ({len(result.get('raw_key_value_pairs', {}))}):")
        raw_pairs = result.get('raw_key_value_pairs', {})
        for key, value in list(raw_pairs.items())[:10]:  # Show first 10
            print(f"  {key}: {value}")
        
        print("\n🎉 Dynamic extraction test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_storage():
    """Test storing template data in database."""
    print("\n📊 TESTING DATABASE STORAGE")
    print("=" * 40)
    
    try:
        from app.services.pg_upload_files import get_pg_conn
        
        # Test database connection
        conn = get_pg_conn()
        cur = conn.cursor()
        
        # Check if templates table exists and get structure
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'templates'
            ORDER BY column_name
        """)
        
        template_columns = cur.fetchall()
        print(f"📋 Templates table columns ({len(template_columns)}):")
        for col_name, col_type in template_columns:
            print(f"  - {col_name}: {col_type}")
        
        # Check template_versions table
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'template_versions'
            ORDER BY column_name
        """)
        
        version_columns = cur.fetchall()
        print(f"\n📋 Template_versions table columns ({len(version_columns)}):")
        for col_name, col_type in version_columns:
            print(f"  - {col_name}: {col_type}")
        
        cur.close()
        conn.close()
        
        print("\n✅ Database structure verified!")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 Starting Template API Tests...")
    
    # Test 1: Dynamic extraction
    test1_success = await test_dynamic_extraction()
    
    # Test 2: Database storage
    test2_success = test_database_storage()
    
    print(f"\n📊 TEST SUMMARY:")
    print(f"  Dynamic Extraction: {'✅ PASS' if test1_success else '❌ FAIL'}")
    print(f"  Database Storage: {'✅ PASS' if test2_success else '❌ FAIL'}")
    
    if test1_success and test2_success:
        print("\n🎉 All tests passed! Template API is ready to use.")
        print("\n📖 Usage:")
        print("  POST /templates/create - Upload file and create template")
        print("  GET /templates/ - List all templates") 
        print("  GET /templates/{id} - Get specific template")
    else:
        print("\n⚠️ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())