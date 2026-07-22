import os
import requests
import json
from dotenv import load_dotenv

load_dotenv('.env')
api_key = os.getenv("NVIDIA_API_KEY")

headers = {
    'Authorization': f'Bearer {api_key}',
    'Accept': 'application/json'
}

prompt_text = (
    "Extract all major regions/rooms/zones with their bounding boxes "
    "(format [ymin, xmin, ymax, xmax] normalized 0.0 to 1.0) and spatial "
    "relationship to the largest region in the image in strict JSON format. "
    "JSON should be an object with a 'regions' key containing an array of objects "
    "with keys: 'label', 'bbox', and 'spatial_relationship_to_largest'.\n"
    "CRITICAL: Output ONLY the JSON object. Do not output any reasoning, chain of thought, or explanations."
)

p = {
    'model': 'meta/llama-3.2-11b-vision-instruct',
    'messages': [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt_text},
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAQDAwQDAwQEAwQFBAQFBgoHBgYGBg0JCggKDw0QEA8NDw4RExgUERIGEg4PExoUFhcXGxsbEBQZHxweGxweGxz/2wBDAQQFBQYGBgwHBwwXEQ4RFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxf/wAARCABQAFADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFgEBAQEAAAAAAAAAAAAAAAAAAAUH/8QAFREBAQAAAAAAAAAAAAAAAAAAABH/2gAMAwEAAhEDEQA/AL+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//Z'}}
            ]
        }
    ],
    "temperature": 0.2,
    "max_tokens": 1024
}

r = requests.post('https://integrate.api.nvidia.com/v1/chat/completions', headers=headers, json=p)
print(r.status_code)
print(r.text)
