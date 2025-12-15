#!/usr/bin/env python3
"""
Test OpenAI connection using the actual app modules
"""
import sys
sys.path.append('/home/ditsdev370/Project/EOB835')

from app.services.ai_claim_extractor import ai_extract_claims, OPENAI_AVAILABLE, OPENAI_API_KEY

# Test text from EOB
test_text = """
MEMBER BOUFFARD, JUDITH H. NUMBER 04007-996949371-00 ACCOUNT NO. 2569
CLAIM NO. EVC 29768907-00
DIAG L22 S31829A S31819A R32
DOS PROC U CLAIMED MEM RESP DEDUCT INELIG-MEM INELIG-PROV CODE DISCOUNT SEQSTR AMOUNT PAID
10/08/25 99308 01 90.89 18.75B 28.39 0888 .87 42.88
CLAIM TOTAL 90.89 18.75 28.39 .87 42.88
"""

print("="*60)
print("🧪 TESTING AI EXTRACTION IN APP CONTEXT")
print("="*60)

print(f"🤖 OpenAI Available: {OPENAI_AVAILABLE}")
print(f"🔑 API Key Present: {bool(OPENAI_API_KEY)}")

if OPENAI_API_KEY:
    print(f"📝 Key Length: {len(OPENAI_API_KEY)}")
    print(f"📝 Key Preview: {OPENAI_API_KEY[:10]}...{OPENAI_API_KEY[-10:]}")

print("\n" + "="*60)
print("🔥 RUNNING AI EXTRACTION TEST...")
print("="*60)

# Run the actual extraction function
result = ai_extract_claims(test_text)

print("\n📊 EXTRACTION RESULT:")
print("="*60)
import json
print(json.dumps(result, indent=2, default=str))

print("\n🔍 ANALYSIS:")
print(f"✅ Claims Found: {len(result.get('claims', []))}")
print(f"🎯 Confidence: {result.get('confidence', 0)}%")
print(f"🏥 Payer: {result.get('payer_info', {}).get('name', 'Unknown')}")
print(f"💰 Payment Amount: ${result.get('payment', {}).get('payment_amount', 0)}")

if result.get('error'):
    print(f"❌ Error: {result.get('error')}")
elif result.get('claims'):
    print("✅ AI Extraction SUCCESS!")
else:
    print("⚠️  Using Fallback Extraction")

print("="*60)