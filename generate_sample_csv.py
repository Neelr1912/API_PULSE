"""Generate sample API log CSV for API-Pulse (600 rows)."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROUTES = [
    "/api/users",
    "/api/users/{id}",
    "/api/products",
    "/api/products/{id}",
    "/api/orders",
    "/api/orders/{id}",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/cart",
    "/api/payments",
]

METHOD_WEIGHTS = [("GET", 0.50), ("POST", 0.25), ("PUT", 0.15), ("DELETE", 0.10)]
STATUS_WEIGHTS = [
    (200, 0.55),
    (201, 0.15),
    (400, 0.10),
    (404, 0.08),
    (500, 0.08),
    (503, 0.04),
]

OUTLIER_COUNT = 30
ROW_COUNT = 600
RNG = random.Random(42)


def weighted_choice(options: list[tuple]) -> object:
    r = RNG.random()
    cumulative = 0.0
    for value, weight in options:
        cumulative += weight
        if r <= cumulative:
            return value
    return options[-1][0]


def latency_for_route(route: str, is_outlier: bool) -> int:
    if is_outlier:
        return RNG.randint(2000, 6000)
    if route == "/api/auth/logout":
        return RNG.randint(50, 120)
    if route == "/api/payments":
        return RNG.randint(800, 4000)
    return RNG.randint(80, 900)


def payload_for_method(method: str) -> int:
    if method == "GET":
        return RNG.randint(200, 2000)
    if method in ("POST", "PUT"):
        return RNG.randint(1000, 50000)
    if method == "DELETE":
        return RNG.randint(100, 500)
    return RNG.randint(200, 5000)


def random_timestamp(now: datetime) -> str:
    days_ago = RNG.randint(0, 29)
    hour = RNG.randint(0, 23)
    minute = RNG.randint(0, 59)
    second = RNG.randint(0, 59)
    ts = now - timedelta(days=days_ago)
    ts = ts.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def build_rows() -> list[dict]:
    now = datetime.now(timezone.utc)
    outlier_indices = set(RNG.sample(range(ROW_COUNT), OUTLIER_COUNT))
    rows: list[dict] = []

    for i in range(ROW_COUNT):
        route = ROUTES[i % len(ROUTES)] if i < len(ROUTES) else RNG.choice(ROUTES)
        # Ensure all routes appear; still randomize heavily
        if i >= len(ROUTES):
            route = RNG.choice(ROUTES)
        method = weighted_choice(METHOD_WEIGHTS)
        status_code = weighted_choice(STATUS_WEIGHTS)
        is_outlier = i in outlier_indices
        rows.append(
            {
                "route": route,
                "method": method,
                "status_code": status_code,
                "response_time_ms": latency_for_route(route, is_outlier),
                "payload_size_bytes": payload_for_method(method),
                "timestamp": random_timestamp(now),
            }
        )

    # Shuffle so route order is not sequential
    RNG.shuffle(rows)
    return rows


def main() -> None:
    root = Path(__file__).resolve().parent
    out_dir = root / "sample_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sample_api_logs.csv"

    df = pd.DataFrame(build_rows())
    assert len(df) == ROW_COUNT, f"Expected {ROW_COUNT} rows, got {len(df)}"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
    print(f"Unique routes: {df['route'].nunique()}")


if __name__ == "__main__":
    main()
