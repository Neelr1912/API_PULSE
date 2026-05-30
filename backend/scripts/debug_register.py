import asyncio
import sys
import traceback

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv("../.env")

async def test():
    from database import engine, AsyncSessionLocal
    from models import User
    from auth.utils import hash_password
    from sqlalchemy import text, select

    # 1. Test DB connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("[OK] DB connection works")
    except Exception as e:
        print(f"[FAIL] DB connection: {type(e).__name__}: {e}")
        return

    # 2. Check if users table exists
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='users'")
            )
            count = result.scalar()
            print(f"[INFO] users table exists: {bool(count)}")
    except Exception as e:
        print(f"[FAIL] table check: {type(e).__name__}: {e}")

    # 3. Test bcrypt
    try:
        h = hash_password("testpassword")
        print(f"[OK] bcrypt hash works: {h[:30]}...")
    except Exception as e:
        print(f"[FAIL] hash_password: {type(e).__name__}: {e}")
        traceback.print_exc()

    # 4. Check SECRET_KEY is loaded
    import os
    sk = os.getenv("SECRET_KEY", "")
    print(f"[INFO] SECRET_KEY loaded: {bool(sk)} (len={len(sk)})")

    # 5. Simulate register flow
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.email == "debug@test.com")
            )
            existing = result.scalar_one_or_none()
            if existing:
                print(f"[INFO] Test user already exists: id={existing.id}")
            else:
                u = User(
                    username="debugtest",
                    email="debug@test.com",
                    hashed_password=hash_password("testpass"),
                )
                session.add(u)
                await session.flush()
                await session.refresh(u)
                await session.commit()
                print(f"[OK] User inserted: id={u.id}, username={u.username}")
    except Exception as e:
        print(f"[FAIL] register flow: {type(e).__name__}: {e}")
        traceback.print_exc()

asyncio.run(test())
