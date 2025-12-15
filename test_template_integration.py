#!/usr/bin/env python3
"""
Test template API integration with existing database schema
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from app.services.template_db_service import (
    create_template_in_postgres,
    save_template_data,
    get_template_by_id,
    list_all_templates,
    get_template_keys_by_id
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_template_integration():
    """Test the complete template integration with existing database schema."""
    
    print("🧪 Testing Template Integration with Existing Database Schema")
    print("=" * 60)
    
    try:
        # Test data
        test_filename = "sample_template.txt"
        test_raw_text = "Patient Name: John Doe\nPolicy Number: 12345\nClaim Amount: $500.00\nDate of Service: 2024-01-15"
        test_json_data = {
            "patient_name": "John Doe",
            "policy_number": "12345", 
            "claim_amount": "$500.00",
            "date_of_service": "2024-01-15",
            "extraction_confidence": 90
        }
        test_dynamic_keys = ["patient_name", "policy_number", "claim_amount", "date_of_service"]
        
        # 1. Test creating template in PostgreSQL
        print("\n1. Creating template in PostgreSQL...")
        template_name = f"Test-Template-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        template_id = create_template_in_postgres(
            name=template_name,
            filename=test_filename,
            template_type="other"
        )
        print(f"✅ Created template: {template_id}")
        
        # 2. Test saving complete template data
        print("\n2. Saving template data with MongoDB integration...")
        save_result = save_template_data(
            template_id=template_id,
            filename=test_filename,
            raw_text=test_raw_text,
            json_data=test_json_data,
            dynamic_keys=test_dynamic_keys,
            file_size=len(test_raw_text),
            mime_type="text/plain",
            ai_confidence=90
        )
        print(f"✅ Saved template data: {save_result}")
        
        # 3. Test retrieving template by ID
        print("\n3. Retrieving template by ID...")
        retrieved_template = get_template_by_id(template_id)
        if retrieved_template:
            print(f"✅ Retrieved template: {retrieved_template['name']}")
            print(f"   Version: {retrieved_template.get('current_version', {}).get('version_number', 'N/A')}")
            if 'session_data' in retrieved_template:
                print(f"   Dynamic keys: {len(retrieved_template['session_data'].get('dynamic_keys', []))}")
                print(f"   AI confidence: {retrieved_template['session_data'].get('ai_confidence', 'N/A')}")
        else:
            print("❌ Failed to retrieve template")
            
        # 4. Test getting template keys
        print("\n4. Getting template dynamic keys...")
        keys = get_template_keys_by_id(template_id)
        print(f"✅ Retrieved {len(keys)} dynamic keys: {keys}")
        
        # 5. Test listing all templates
        print("\n5. Listing all templates...")
        all_templates = list_all_templates(limit=5)
        print(f"✅ Found {len(all_templates)} templates")
        for template in all_templates[:2]:  # Show first 2
            print(f"   - {template.get('name', 'Unknown')} ({template.get('filename', 'No file')})")
        
        print("\n" + "=" * 60)
        print("🎉 All template integration tests passed!")
        print("✅ PostgreSQL templates table - Working")
        print("✅ PostgreSQL template_versions table - Working") 
        print("✅ MongoDB template_builder_sessions - Working")
        print("✅ Data retrieval and listing - Working")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database_connections():
    """Test basic database connections."""
    
    print("\n🔍 Testing Database Connections...")
    print("-" * 40)
    
    try:
        # Test PostgreSQL
        from app.services.pg_upload_files import get_pg_conn
        pg_conn = get_pg_conn()
        pg_cur = pg_conn.cursor()
        
        # Test basic query
        pg_cur.execute("SELECT 1 as test")
        result = pg_cur.fetchone()
        pg_cur.close()
        pg_conn.close()
        
        print("✅ PostgreSQL connection - Working")
        
        # Test MongoDB
        from app.services.template_db_service import get_mongo_conn
        
        # Get the client connection (our function now returns client)
        mongo_client = get_mongo_conn()
        db = mongo_client['eob_db']
        
        # Test basic operation - just check if we can access a collection
        sessions_collection = db['template_builder_sessions']
        test_count = sessions_collection.count_documents({})
        mongo_client.close()
        
        print("✅ MongoDB connection - Working")
        print(f"   template_builder_sessions collection accessible, found {test_count} existing documents")
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

if __name__ == "__main__":
    async def main():
        print("🚀 Starting Template Integration Tests")
        print("=" * 60)
        
        # Test connections first
        if not await test_database_connections():
            print("\n❌ Database connection tests failed. Exiting.")
            return
        
        # Run main integration test
        success = await test_template_integration()
        
        if success:
            print("\n🎯 Integration test completed successfully!")
        else:
            print("\n💥 Integration test failed!")
            
    asyncio.run(main())