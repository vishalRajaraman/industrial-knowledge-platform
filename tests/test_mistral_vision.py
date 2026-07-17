import os
import sys
import base64
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("NVIDIA_API_KEY")
base_url = "https://integrate.api.nvidia.com/v1"
model = os.getenv("LLM_MODEL", "mistralai/mistral-medium-3.5-128b")

print(f"Testing model: {model}")

client = OpenAI(base_url=base_url, api_key=api_key)

try:
    with open(r"C:\Users\vishal rajaraman\Desktop\industrial_eng_diagram.jpeg", "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
except Exception as e:
    print(f"Failed to read image: {e}")
    sys.exit(1)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract all rooms with their bounding boxes (format [ymin, xmin, ymax, xmax]) and spatial relationship to the largest room in the image in JSON format."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
        ]
    }
]

try:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=1000
    )
    print("SUCCESS")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"FAILED: {e}")
