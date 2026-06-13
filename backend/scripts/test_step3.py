"""
Step 3 API verification script.
Usage (from api-pulse/, with server running on :8000):
  cd backend && python scripts/test_step3.py

Required env:
  TEST_PASSWORD=your_password

Optional env:
  API_BASE=http://127.0.0.1:8000
  TEST_EMAIL=upload@test.com
  TEST_USERNAME=step3user
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
EMAIL = os.getenv("TEST_EMAIL", "step3@test.com")
PASSWORD = os.getenv("TEST_PASSWORD", "")
USERNAME = os.getenv("TEST_USERNAME", "step3user")
ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "sample_logs" / "sample_api_logs.csv"


def main() -> int:
    if not PASSWORD:
        print("ERROR: Set TEST_PASSWORD environment variable before running tests.")
        return 1
    print("=== Step 3 API tests ===\n")
    failures = 0

    # 1 — CSV row count (local file)
    if not CSV_PATH.is_file():
        print("FAIL 1: sample_api_logs.csv missing — run: python generate_sample_csv.py")
        failures += 1
    else:
        import pandas as pd

        n = len(pd.read_csv(CSV_PATH))
        ok = n == 600
        print(f"{'PASS' if ok else 'FAIL'} 1: sample CSV rows = {n} (expected 600)")
        if not ok:
            failures += 1

    client = httpx.Client(base_url=API_BASE, timeout=60.0)

    # 3 — no token -> 401
    r = client.post("/upload/csv", files={"file": ("x.csv", b"a,b", "text/csv")})
    ok = r.status_code == 401
    print(f"{'PASS' if ok else 'FAIL'} 3: POST /upload/csv no token -> {r.status_code}")
    if not ok:
        failures += 1

    # Register + login
    client.post(
        "/auth/register",
        json={"username": USERNAME, "email": EMAIL, "password": PASSWORD},
    )
    login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if login.status_code != 200:
        print(f"FAIL: login failed ({login.status_code}) — is the API running? {login.text}")
        return 1
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4 — valid upload -> 200
    if not CSV_PATH.is_file():
        print("SKIP 4–6: no CSV file")
        return failures or 1

    with CSV_PATH.open("rb") as f:
        r = client.post(
            "/upload/csv",
            headers=headers,
            files={"file": ("sample_api_logs.csv", f, "text/csv")},
        )
    ok = r.status_code == 200
    print(f"{'PASS' if ok else 'FAIL'} 4: POST /upload/csv valid file -> {r.status_code}")
    if not ok:
        print(r.text)
        failures += 1
    else:
        body = r.json()
        required = {
            "message",
            "total_rows",
            "inserted_rows",
            "failed_rows",
            "failed_details",
            "routes_detected",
            "upload_id",
        }
        missing = required - set(body)
        if missing:
            print(f"FAIL 4: UploadResponse missing keys: {missing}")
            failures += 1
        else:
            print(
                f"     inserted={body['inserted_rows']}, failed={body['failed_rows']}, "
                f"routes={len(body['routes_detected'])}"
            )

    # 6 — history
    r = client.get("/upload/history", headers=headers)
    ok = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) >= 1
    print(f"{'PASS' if ok else 'FAIL'} 6: GET /upload/history -> {r.status_code}, count={len(r.json()) if r.status_code == 200 else 0}")
    if not ok:
        failures += 1

    print("\nNote: Run `alembic upgrade head` and check api_logs in DB for tests 2 & 5.")
    print(f"{'All automated API checks passed.' if not failures else f'{failures} check(s) failed.'}")
    return failures


if __name__ == "__main__":
    sys.exit(main())
