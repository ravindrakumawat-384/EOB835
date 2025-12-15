#!/usr/bin/env python3
"""
Test script to extract payer data from template JSON and save to payer table.

This script demonstrates:
1. Processing existing template JSON data in MongoDB
2. Extracting payer information from JSON fields
3. Saving payer data to PostgreSQL payers table
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.template_db_service import (
    process_existing_templates_for_payer_data,
    extract_and_save_payer_data
)
from app.services.pg_upload_files import get_pg_conn
from app.utils.logger import get_logger

logger = get_logger(__name__)

def test_single_payer_extraction():
    """Test extracting payer data from sample JSON."""
    
    # Sample template JSON data with payer information
    sample_template_data = {
        "payer_name": "UnitedHealthcare",
        "payer_code": "UHC001",
        "insurance_company": "United Health Group",
        "plan_name": "UHC Choice Plus",
        "member_id": "123456789",
        "provider_name": "Dr. John Smith",
        "claim_number": "CLM2024001",
        "service_date": "2024-12-01",
        "amount_billed": "$250.00",
        "amount_paid": "$200.00"
    }
    
    print("🧪 Testing single payer extraction...")
    print(f"Sample JSON data: {sample_template_data}")
    
    # Extract and save payer data
    org_id = "9ac493f7-cc6a-4d7d-8646-affb00ed58da"
    payer_id = extract_and_save_payer_data(sample_template_data, org_id)
    
    if payer_id:
        print(f"✅ Successfully created/found payer: {payer_id}")
        
        # Verify payer was saved
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, payer_code, ai_detection_metadata 
            FROM payers 
            WHERE id = %s
        """, (payer_id,))
        
        payer_data = cur.fetchone()
        if payer_data:
            print(f"   Payer ID: {payer_data[0]}")
            print(f"   Payer Name: {payer_data[1]}")
            print(f"   Payer Code: {payer_data[2]}")
            print(f"   AI Metadata: {payer_data[3]}")
        
        cur.close()
        conn.close()
    else:
        print("❌ Failed to extract payer data")

def test_bulk_template_processing():
    """Test processing all existing template data for payer extraction."""
    
    print("\n🔄 Processing all existing template JSON data...")
    
    org_id = "9ac493f7-cc6a-4d7d-8646-affb00ed58da"
    results = process_existing_templates_for_payer_data(org_id)
    
    print(f"📊 Processing Results:")
    print(f"   Templates processed: {results['processed_templates']}")
    print(f"   New payers created: {results['payers_created']}")
    print(f"   Existing payers found: {results['payers_found_existing']}")
    print(f"   Templates without payer data: {results['templates_without_payer_data']}")
    
    if results['errors']:
        print(f"   Errors encountered: {len(results['errors'])}")
        for error in results['errors'][:3]:  # Show first 3 errors
            print(f"     - {error}")

def show_current_payers():
    """Display current payers in the database."""
    
    print("\n📋 Current Payers in Database:")
    
    conn = get_pg_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, name, payer_code, created_at, ai_detection_metadata
        FROM payers 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    payers = cur.fetchall()
    
    if payers:
        for i, payer in enumerate(payers, 1):
            print(f"   {i}. {payer[1]} (Code: {payer[2] or 'N/A'})")
            print(f"      ID: {payer[0]}")
            print(f"      Created: {payer[3]}")
            if payer[4]:  # AI metadata
                metadata = payer[4]
                if isinstance(metadata, dict) and 'source' in metadata:
                    print(f"      Source: {metadata['source']}")
            print()
    else:
        print("   No payers found in database")
    
    cur.close()
    conn.close()

def main():
    """Run the payer extraction tests."""
    
    print("🚀 PAYER DATA EXTRACTION FROM TEMPLATE JSON")
    print("=" * 60)
    
    try:
        # Show current state
        show_current_payers()
        
        # Test single extraction
        test_single_payer_extraction()
        
        # Test bulk processing
        test_bulk_template_processing()
        
        # Show final state
        show_current_payers()
        
        print("\n✅ Payer extraction testing completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        logger.error(f"Payer extraction test failed: {e}")

if __name__ == "__main__":
    main()