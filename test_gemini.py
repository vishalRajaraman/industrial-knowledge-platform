import requests
import json

headers = {
    'Authorization': 'Bearer YOUR_API_KEY_HERE',
    'Accept': 'application/json'
}

p = {
    'model': 'gemini-2.5-flash',
    'messages': [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': 'Are you available?'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAQDAwQDAwQEAwQFBAQFBgoHBgYGBg0JCggKDw0QEA8NDw4RExgUERIGEg4PExoUFhcXGxsbEBQZHxweGxweGxz/2wBDAQQFBQYGBgwHBwwXEQ4RFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxf/wAARCABQAFADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFgEBAQEAAAAAAAAAAAAAAAAAAAUH/8QAFREBAQAAAAAAAAAAAAAAAAAAABH/2gAMAwEAAhEDEQA/AL+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//Z'}}
            ]
        }
    ],
    'max_tokens': 10
}

r = requests.post('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', headers=headers, json=p)
print(r.status_code)
print(r.text)
