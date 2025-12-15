#!/usr/bin/env python3
"""
Script to check MongoDB extraction results and show the JSON data
"""
import json
from pymongo import MongoClient

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["eob835"]
collection = db["extraction_results"]

# Get the latest document
latest_doc = collection.find_one(sort=[("createdAt", -1)])

if latest_doc:
    print("="*80)
    print("🔍 LATEST EXTRACTION RESULT FROM MONGODB:")
    print("="*80)
    
    # Show basic info
    print(f"📄 File ID: {latest_doc.get('fileId')}")
    print(f"📊 Separate Claims Count: {latest_doc.get('separateClaimsCount', 0)}")
    print(f"💰 Total Extracted Amount: ${latest_doc.get('totalExtractedAmount', 0)}")
    print(f"🏥 Payers: {latest_doc.get('payerNames', [])}")
    print(f"📋 Claim Numbers: {latest_doc.get('claimNumbers', [])}")
    print(f"🎯 AI Confidence: {latest_doc.get('aiConfidence', 0)}%")
    print(f"✅ Extraction Status: {latest_doc.get('extractionStatus', 'unknown')}")
    
    print("\n" + "="*80)
    print("🤖 ORIGINAL AI RESULT:")
    print("="*80)
    ai_result = latest_doc.get('originalAiResult', {})
    print(json.dumps(ai_result, indent=2, default=str))
    
    print("\n" + "="*80)
    print("📋 NORMALIZED CLAIMS (SEPARATE RECORDS):")
    print("="*80)
    claims = latest_doc.get('normalizedClaims', [])
    for i, claim in enumerate(claims, 1):
        print(f"\n--- CLAIM {i} ---")
        print(json.dumps(claim, indent=2, default=str))
    
    print("\n" + "="*80)
    print(f"✅ SUMMARY: Found {len(claims)} separate claims in MongoDB")
    print("="*80)
else:
    print("❌ No extraction results found in MongoDB")