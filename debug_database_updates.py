#!/usr/bin/env python3
"""
Diagnostic script to debug why database updates are failing during file processing.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.pg_upload_files import (
    update_file_status, 
    mark_processing_failed, 
    check_database_schema,
    test_database_update
)

def main():
    print("🔬 DATABASE UPDATE DIAGNOSTIC TOOL")
    print("=" * 50)
    
    # Step 1: Check database schema
    print("\n1️⃣ CHECKING DATABASE SCHEMA...")
    schema_info = check_database_schema()
    
    if "error" in schema_info:
        print(f"❌ Schema check failed: {schema_info['error']}")
        return
    
    print("✅ Database schema check results:")
    print(f"   - Table exists: {schema_info['table_exists']}")
    print(f"   - All columns: {[col[0] for col in schema_info['all_columns']]}")
    print(f"   - Missing required columns: {schema_info['missing_columns']}")
    
    if schema_info['missing_columns']:
        print(f"\n⚠️  WARNING: Missing columns detected: {schema_info['missing_columns']}")
        print("   Please add these columns to your upload_files table:")
        for col in schema_info['missing_columns']:
            if col == 'processing_error_message':
                print(f"   ALTER TABLE upload_files ADD COLUMN {col} TEXT;")
            elif col == 'updated_at':
                print(f"   ALTER TABLE upload_files ADD COLUMN {col} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;")
    
    # Step 2: Test database connection and updates
    print("\n2️⃣ TESTING DATABASE UPDATE FUNCTIONALITY...")
    test_result = test_database_update()
    
    if not test_result:
        print("❌ Database update test failed")
        return
    
    # Step 3: Test with real file IDs from database
    print("\n3️⃣ TESTING WITH REAL FILE DATA...")
    if schema_info['sample_data']:
        print("📋 Found existing files in database:")
        for i, (file_id, status, error_msg) in enumerate(schema_info['sample_data'], 1):
            print(f"   {i}. ID: {file_id}, Status: {status}, Error: {error_msg}")
        
        # Test updating the first file
        if schema_info['sample_data']:
            first_file_id = schema_info['sample_data'][0][0]
            print(f"\n🧪 Testing update on real file: {first_file_id}")
            
            # Test regular status update
            result1 = update_file_status(first_file_id, "test_diagnostic", "Diagnostic test message")
            print(f"   Regular update result: {result1}")
            
            # Test processing failed update
            result2 = mark_processing_failed(first_file_id, "Diagnostic test error", "diagnostic_test")
            print(f"   Processing failed update result: {result2}")
            
            # Restore original status
            original_status = schema_info['sample_data'][0][1] or "pending_review"
            update_file_status(first_file_id, original_status)
            print(f"   Restored original status: {original_status}")
    
    # Step 4: Check common issues
    print("\n4️⃣ CHECKING COMMON ISSUES...")
    
    # Check if file IDs are being generated correctly
    print("📝 Common issues to check:")
    print("   1. File ID format - Make sure MD5 hashes are being used correctly")
    print("   2. Database permissions - Ensure user has UPDATE permissions")
    print("   3. Column names - Verify processing_error_message column exists")
    print("   4. Connection settings - Check database connection parameters")
    
    print("\n✅ DIAGNOSTIC COMPLETE!")
    print("If updates are still failing, check:")
    print("- Database server logs")
    print("- Application logs during file upload")
    print("- Network connectivity to database")

if __name__ == "__main__":
    main()