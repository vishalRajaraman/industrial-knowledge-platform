import os
import json
from openai import OpenAI

# Assuming Ollama is running locally on port 11434 with OpenAI compatible API
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama" # required, but unused
)

def json_chat(prompt: str, system: str = "", temperature: float = 0.0) -> dict:
    """
    Send a chat request to Ollama and expect JSON back.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Ollama JSON chat error: {e}")
        return {}
