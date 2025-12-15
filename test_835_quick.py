#!/usr/bin/env python3

"""
Quick test to generate 835 file with debug output
"""

import requests
import json

def test_835_generation():
    """Test the 835 generation with the existing claim ID"""
    
    url = "http://localhost:8001/generate-835/"
    
    # Use the claim ID that was referenced in the output
    payload = {
        "claim_id": "03d3e06b-2dbc-4eb5-8055-c8e28d10d266",
        "org_id": "123e4567-e89b-12d3-a456-426614174000",
        "generated_by": "456e7890-e89b-12d3-a456-426614174001"
    }
    
    print(f"🧪 Testing 835 generation with debug output...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload)
        
        print(f"\n📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            print(f"Export ID: {data.get('export_id')}")
            print(f"File Name: {data.get('file_name')}")
            print(f"S3 Path: {data.get('s3_path')}")
            print(f"Claim Number: {data.get('claim_number')}")
            print(f"Total Amount: ${data.get('total_amount')}")
            print(f"Status: {data.get('status')}")
            
        else:
            print(f"❌ Error {response.status_code}:")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
            except:
                print(response.text)
                
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_835_generation()