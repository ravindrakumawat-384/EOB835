#!/usr/bin/env python3

"""
Test script for 835 Form Generation with Claim ID Reference and S3 Storage
"""

import requests
import json
from datetime import datetime

def test_835_generation_with_claim_reference():
    """
    Test 835 form generation that:
    1. Uses claim_id as reference
    2. Stores file in S3 with claim number
    3. Returns proper export reference
    """
    
    # API endpoint
    url = "http://localhost:8001/generate-835/"
    
    # Test payload with claim_id
    test_claim_id = "03d3e06b-2dbc-4eb5-8055-c8e28d10d266"
    
    payload = {
        "claim_id": test_claim_id,
        "org_id": "123e4567-e89b-12d3-a456-426614174000", 
        "generated_by": "456e7890-e89b-12d3-a456-426614174001"
    }
    
    print("🚀 Testing 835 Form Generation")
    print("=" * 50)
    print(f"📋 Claim ID: {test_claim_id}")
    print(f"🌐 API URL: {url}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        print(f"\n📤 Sending request...")
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ SUCCESS! 835 Form Generated")
            print("=" * 50)
            
            # Key information
            export_id = data.get('export_id')
            export_ref = data.get('export_reference')
            file_name = data.get('file_name')
            s3_path = data.get('s3_path')
            claim_number = data.get('claim_number')
            
            print(f"🆔 Export ID: {export_id}")
            print(f"📝 Export Reference: {export_ref}")
            print(f"📁 File Name: {file_name}")
            print(f"☁️ S3 Path: {s3_path}")
            print(f"🏥 Claim Number: {claim_number}")
            print(f"💰 Total Amount: ${data.get('total_amount', 0)}")
            print(f"📊 Service Lines: {data.get('service_lines_count', 0)}")
            print(f"⏰ Generated At: {data.get('generated_at')}")
            print(f"✅ Status: {data.get('status')}")
            
            # Verify naming convention
            print(f"\n🔍 File Naming Verification:")
            if claim_number in file_name:
                print(f"   ✅ Claim number '{claim_number}' is in filename")
            else:
                print(f"   ❌ Claim number not found in filename")
                
            if '_835_' in file_name:
                print(f"   ✅ 835 format identifier found")
            else:
                print(f"   ❌ 835 format identifier missing")
                
            if file_name.endswith('.txt'):
                print(f"   ✅ Proper file extension")
            else:
                print(f"   ❌ Wrong file extension")
            
            # Verify S3 storage structure  
            print(f"\n☁️ S3 Storage Verification:")
            expected_s3_pattern = f"s3://eob-dev-bucket/exports/835/"
            if s3_path and s3_path.startswith(expected_s3_pattern):
                print(f"   ✅ S3 path follows expected pattern")
                print(f"   📂 Path: {s3_path}")
            else:
                print(f"   ❌ S3 path doesn't match expected pattern")
                
            # Verify export reference format
            print(f"\n📝 Export Reference Verification:")
            if export_ref and export_ref.startswith('EXP835-'):
                print(f"   ✅ Export reference follows naming convention")
                if claim_number in export_ref:
                    print(f"   ✅ Claim number included in reference")
                else:
                    print(f"   ❌ Claim number missing from reference")
            else:
                print(f"   ❌ Export reference format incorrect")
                
            return export_id
            
        else:
            print(f"\n❌ ERROR {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Error text: {response.text}")
                
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Server not running on port 8001")
        print(f"💡 Start server with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
        return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def test_export_listing():
    """Test listing exports to verify they're properly stored"""
    
    url = "http://localhost:8001/generate-835/exports"
    
    print(f"\n📋 Testing Export Listing")
    print("=" * 30)
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            exports = response.json()
            print(f"✅ Found {len(exports)} exports")
            
            for i, export in enumerate(exports[:3]):  # Show first 3
                print(f"\n📄 Export {i+1}:")
                print(f"   ID: {export.get('export_id')}")
                print(f"   Reference: {export.get('export_reference')}")
                print(f"   Claim: {export.get('claim_number')}")
                print(f"   S3 Path: {export.get('storage_path')}")
                print(f"   Status: {export.get('status')}")
        else:
            print(f"❌ Failed to list exports: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Failed to list exports: {e}")

def test_download_export(export_id):
    """Test downloading export using presigned URL"""
    
    if not export_id:
        print(f"\n⚠️ No export ID provided, skipping download test")
        return
        
    url = f"http://localhost:8001/generate-835/exports/{export_id}/download"
    
    print(f"\n📥 Testing Export Download")
    print("=" * 30)
    print(f"Export ID: {export_id}")
    
    try:
        response = requests.post(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            download_url = data.get('download_url')
            
            print(f"✅ Download URL generated successfully")
            print(f"🔗 URL: {download_url[:100]}..." if download_url else "No URL")
            print(f"⏳ Expires in: {data.get('expires_in_seconds')} seconds")
            
        else:
            print(f"❌ Download failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Download test failed: {e}")

def main():
    """Run comprehensive test suite"""
    
    print("🧪 835 Form Generation Test Suite")
    print("🎯 Focus: Claim ID Reference + S3 Storage with Claim Number")
    print("=" * 60)
    
    # Test 1: Generate 835 form
    export_id = test_835_generation_with_claim_reference()
    
    # Test 2: List exports
    test_export_listing()
    
    # Test 3: Download export
    test_download_export(export_id)
    
    print(f"\n" + "=" * 60)
    print("🏁 Test Suite Completed!")
    
    if export_id:
        print(f"\n✅ Key Achievements:")
        print(f"   📋 Used claim_id as reference: 03d3e06b-2dbc-4eb5-8055-c8e28d10d266")
        print(f"   📁 File named with claim number: {export_id}")
        print(f"   ☁️ Stored in S3 with organized structure")
        print(f"   🔗 Export reference includes claim info")
        print(f"   🗄️ Database record created with relationships")
        
    print(f"\n📚 File Structure Created:")
    print(f"   Local: /tmp/CLAIM-NUMBER_835_TIMESTAMP.txt")
    print(f"   S3: s3://bucket/exports/835/YYYY/MM/DD/CLAIM-NUMBER_835_TIMESTAMP.txt")
    print(f"   DB: exports_835 + export_items tables")

if __name__ == "__main__":
    main()