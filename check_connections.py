import urllib.request
import json

def check_url(url, method="GET", data=None):
    try:
        req = urllib.request.Request(url, method=method)
        if data:
            req.add_header('Content-Type', 'application/json')
            req.data = json.dumps(data).encode('utf-8')
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.URLError as e:
        return getattr(e, 'code', str(e)), str(e)
    except Exception as e:
        return "Error", str(e)

def main():
    print("Testing API Gateway Health...")
    status, text = check_url("http://localhost:8100/api/v1/system/health")
    print(f"Gateway Health: {status}")

    print("Testing Frontend Static Serve...")
    status, text = check_url("http://localhost:8100/")
    print(f"Frontend Static: {status}")
    if status == 200:
        print("Frontend HTML loaded successfully.")

    print("Testing Orchestrator Health...")
    status, text = check_url("http://localhost:8000/health")
    print(f"Orchestrator Health: {status}")
    if status == 200:
        print(text[:100] + "...")

    print("Testing Orchestrator Query...")
    status, text = check_url("http://localhost:8000/query", method="POST", data={
        "query": "hello",
        "user_role": "operator"
    })
    print(f"Orchestrator Query: {status}")
    if status == 200:
        print(text[:200] + "...")
    else:
        print("Query output:", text)

if __name__ == "__main__":
    main()
