"""Test PostgreSQL connection using DATABASE_URL from api-pulse/.env"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

load_dotenv(ROOT / ".env")


async def main() -> int:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("FAIL: DATABASE_URL is not set in api-pulse/.env")
        return 1

    # Mask password in output
    display = url
    if "@" in url:
        try:
            prefix, rest = url.split("://", 1)
            creds, hostpart = rest.rsplit("@", 1)
            user = creds.split(":")[0]
            display = f"{prefix}://{user}:****@{hostpart}"
        except ValueError:
            pass
    print(f"Connecting to {display} ...")

    try:
        from database import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("PASS: Database connection OK")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}")
        print()
        print("How to fix:")
        print("  1. Ensure PostgreSQL is running (Services -> postgresql-x64-...)")
        print("  2. Edit api-pulse/.env -> DATABASE_URL with YOUR postgres password")
        print("     Example: postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/api_pulse")
        print("  3. Create DB:  CREATE DATABASE api_pulse;")
        return 1
    finally:
        from database import engine

        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
