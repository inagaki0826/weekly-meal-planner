from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

def generate(prompt: str, json_mode: bool = False) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if json_mode else "text/plain"
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config
    )
    return response.text
