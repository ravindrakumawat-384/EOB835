#!/usr/bin/env python3
"""
Script to test OpenAI API connection
"""
import os
import sys

# Add the app directory to the path
sys.path.append('/home/ditsdev370/Project/EOB835')

from app.services.ai_claim_extractor import OPENAI_AVAILABLE

print("="*60)
print("🔍 OPENAI API CONNECTION TEST")
print("="*60)

# Check if OpenAI package is available
try:
    import openai
    print("✅ OpenAI package is installed")
    print(f"📦 OpenAI version: {openai.__version__}")
except ImportError as e:
    print("❌ OpenAI package not found:", e)
    exit(1)

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Check API key
api_key = os.getenv("OPENAI_API_KEY")
print(f"\n🔑 API Key Status:")
if api_key:
    print(f"✅ OPENAI_API_KEY is loaded from .env (length: {len(api_key)})")
    print(f"📝 Key preview: {api_key[:8]}...{api_key[-8:] if len(api_key) > 16 else '***'}")
else:
    print("❌ OPENAI_API_KEY not found in .env file")

print(f"\n🤖 AI Extraction Available: {'✅ YES' if OPENAI_AVAILABLE else '❌ NO'}")

# Test API connection if key is available
if api_key and OPENAI_AVAILABLE:
    print("\n🧪 Testing API Connection...")
    try:
        client = openai.OpenAI(
            api_key=api_key
        )
        
        # Simple test request  
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello! Just testing API connection. Respond with 'API Working'."}],
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip()
        print(f"✅ API Connection Successful!")
        print(f"📤 Test Response: {result}")
        
    except Exception as e:
        print(f"❌ API Connection Failed: {e}")
        print("💡 Check your API key and internet connection")

print("\n" + "="*60)