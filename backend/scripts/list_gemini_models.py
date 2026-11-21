"""List the Gemini models your API key can use.

Run from the backend/ folder:   python -m scripts.list_gemini_models
Use this if you get a "model not found" error: copy a name (without the
"models/" prefix) into GEMINI_MODEL in your .env file.
"""

import sys

from app.config import get_settings


def main() -> int:
    key = get_settings().gemini_api_key
    if not key or not key.strip():
        print("GEMINI_API_KEY is not set in backend/.env")
        return 1

    from google import genai

    client = genai.Client(api_key=key.strip())
    for model in client.models.list():
        print(model.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
