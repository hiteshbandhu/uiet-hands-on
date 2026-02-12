"""Test GEMINI_API_KEY - run this after adding the key to .env"""
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("GEMINI_API_KEY")
if not key:
    print("ERROR: GEMINI_API_KEY not set in .env")
    print("Add: GEMINI_API_KEY=your_key_from_aistudio_google_apikey")
    exit(1)

print("Testing Gemini API key...")
try:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Say 'OK' in one word.",
    )
    text = response.text.strip()
    print(f"Success! Model responded: {text}")
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
