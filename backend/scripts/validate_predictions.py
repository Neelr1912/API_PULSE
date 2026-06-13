import os
import httpx

API_BASE = "http://127.0.0.1:8080"
EMAIL = os.getenv("TEST_EMAIL", "step3@test.com")
PASSWORD = os.getenv("TEST_PASSWORD", "")

def run_tests():
    if not PASSWORD:
        print("ERROR: Set TEST_PASSWORD environment variable before running tests.")
        return
    print("=== Validation Testing ===")
    
    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        # 1. Check Swagger
        res = client.get("/openapi.json")
        if res.status_code == 200:
            openapi = res.json()
            paths = openapi.get("paths", {})
            print("Swagger endpoints registered:")
            for p in paths:
                if "/api/predict" in p:
                    print("  -", p)
        else:
            print("Failed to load openapi.json")

        # 2. Login
        login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            print("Failed to login!")
            return
        
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. GET /api/predict/routes
        print("\nTesting GET /api/predict/routes...")
        res = client.get("/api/predict/routes", headers=headers)
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"Returned {len(data)} routes.")
            if data:
                print("Sample:", data[0])

        # 4. GET /api/predict/top-risks
        print("\nTesting GET /api/predict/top-risks...")
        res = client.get("/api/predict/top-risks", headers=headers)
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"Returned {len(data)} routes.")
            if data:
                print("Top Risk:", data[0])

if __name__ == '__main__':
    run_tests()
