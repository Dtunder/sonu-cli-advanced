import os
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

print("Available models:")
try:
    for m in client.models.list():
        print(f"  • {m.name} ({m.display_name})")
except Exception as e:
    print(f"Error: {e}")
