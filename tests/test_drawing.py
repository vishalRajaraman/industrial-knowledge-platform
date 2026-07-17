import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))

# Add mcp-server to path to import tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp-server")))

from tools.ingestion.drawing_tool import register

# Mock FastMCP
class MockFastMCP:
    def __init__(self):
        self.tools = {}
        
    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator

async def test():
    mcp = MockFastMCP()
    register(mcp)
    
    digitize = mcp.tools["digitize_drawing"]
    
    img_path = r"C:\Users\vishal rajaraman\Desktop\industrial_eng_diagram.jpeg"
    
    print(f"Running digitize_drawing on: {img_path}")
    print("This will test Groq meta-llama/llama-4-scout-17b-16e-instruct...")
    
    try:
        result = await digitize(file_path=img_path, drawing_type="floor_plan")
        
        print("\n--- RESULT ---")
        print(json.dumps(result, indent=2))
        
        if "error" not in result:
            print("\nExtracted Data Summary:")
            for item in result.get("extracted_data", []):
                print(f"- {item['label']}: bbox {item['bbox_px']}, relationship: {item['relationship']}")
                
    except Exception as e:
        print(f"\nError running test: {e}")

if __name__ == "__main__":
    asyncio.run(test())
