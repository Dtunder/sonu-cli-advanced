import os
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY")
print(f"Key loaded: {api_key[:5]}...{api_key[-5:]}")

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents='test',
    )
    print("Success: API Key is valid and model responds via google-genai SDK.")
    print(f"Antwort: {response.text}")
except Exception as e:
    print(f"Error: {e}")
