#!/usr/bin/env python3
"""
Test script to verify the complete file processing error handling workflow.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.pg_upload_files import (
    update_file_status, 
    mark_processing_failed,
    get_pg_conn
)

def test_complete_workflow():
    """Test the complete error handling workflow."""
    print("🧪 TESTING COMPLETE ERROR HANDLING WORKFLOW")
    print("=" * 60)
    
    # Get a real file from database
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, original_filename, processing_status FROM upload_files LIMIT 1")
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if not result:
        print("❌ No files found in database for testing")
        return
    
    file_id, filename, original_status = result
    print(f"📋 Testing with file: {filename}")
    print(f"📋 File ID: {file_id}")
    print(f"📋 Original status: {original_status}")
    
    # Test different failure scenarios
    test_cases = [
        ("text_extraction", "Unable to extract readable text from PDF"),
        ("ai_processing", "OpenAI API returned invalid JSON response"),
        ("validation", "File does not contain expected EOB patterns - only 1 of 6 patterns found"),
        ("database_storage", "Failed to store extraction results in MongoDB: Connection timeout"),
    ]
    
    print(f"\n🔬 Testing {len(test_cases)} failure scenarios...")
    
    for i, (stage, error_msg) in enumerate(test_cases, 1):
        print(f"\n{i}. Testing {stage} failure:")
        print(f"   Error: {error_msg}")
        
        # Mark as processing failed
        success = mark_processing_failed(file_id, error_msg, stage)
        print(f"   Update success: {'✅ YES' if success else '❌ NO'}")
        
        if success:
            # Verify the update
            conn = get_pg_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT processing_status, processing_error_message 
                FROM upload_files WHERE id = %s
            """, (file_id,))
            current_status, current_error = cur.fetchone()
            cur.close()
            conn.close()
            
            print(f"   Current status: {current_status}")
            print(f"   Current error: {current_error}")
    
    # Test successful processing
    print(f"\n✅ Testing successful processing:")
    success = update_file_status(file_id, "processed")
    print(f"   Update success: {'✅ YES' if success else '❌ NO'}")
    
    # Restore original status
    print(f"\n🔄 Restoring original status: {original_status}")
    update_file_status(file_id, original_status)
    
    print(f"\n🎉 WORKFLOW TEST COMPLETED!")

if __name__ == "__main__":
    test_complete_workflow()