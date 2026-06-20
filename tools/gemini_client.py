import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

def generate(prompt: str, json_mode: bool = False) -> str:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    config = {"response_mime_type": "application/json"} if json_mode else {}
    model = genai.GenerativeModel("gemini-2.0-flash", generation_config=config)
    response = model.generate_content(prompt)
    return response.text
