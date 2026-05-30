from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from database import get_db
from models import APILog, User
from schemas import OverviewStats, RouteAnalytics, RouteDetail

router = APIRouter()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _fetch_user_logs_df(db: AsyncSession, user_id: int) -> pd.DataFrame:
    """Load all API logs for a user into a single Pandas DataFrame."""
    result = await db.execute(select(APILog).where(APILog.user_id == user_id))
    rows = result.scalars().all()
    if not rows:
        return pd.DataFrame(
            columns=[
                "route",
                "method",
                "status_code",
                "response_time_ms",
                "payload_size_bytes",
                "timestamp",
            ]
        )

    df = pd.DataFrame(
        [
            {
                "route": r.route,
                "method": r.method,
                "status_code": r.status_code,
                "response_time_ms": float(r.response_time_ms),
                "payload_size_bytes": float(r.payload_size_bytes),
                "timestamp": r.timestamp,
            }
            for r in rows
        ]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def _instability_score(error_rate_percent: float, avg_latency_ms: float, p95_latency_ms: float) -> float:
    error_component = min(error_rate_percent / 100.0, 1.0) * 4.0
    latency_component = min(avg_latency_ms / 2000.0, 1.0) * 3.0
    tail_component = min(p95_latency_ms / 4000.0, 1.0) * 3.0
    return round(min(10.0, error_component + latency_component + tail_component), 2)


def _suggestion(
    error_rate_percent: float,
    avg_latency_ms: float,
    p95_latency_ms: float,
    avg_payload_bytes: float,
) -> str:
    if error_rate_percent > 20:
        return "High failure rate — investigate 5xx errors and add retries"
    if error_rate_percent > 10:
        return "Elevated errors — review input validation and error handling"
    if avg_latency_ms > 2000:
        return "Very high latency — check DB queries and add caching layer"
    if avg_latency_ms > 1000:
        return "High latency — consider Redis caching or DB indexing"
    if p95_latency_ms > 3000:
        return "High tail latency — review slow query logs and timeouts"
    if avg_payload_bytes > 20000:
        return "Large payloads — implement pagination or compression"
    if avg_payload_bytes > 8000:
        return "Medium payloads — consider field filtering or gzip"
    return "Route is healthy — no action needed"


def _trend_for_route(route_df: pd.DataFrame, now: datetime) -> str:
    if route_df.empty:
        return "stable"

    last_start = now - timedelta(days=7)
    prev_start = now - timedelta(days=14)
    prev_end = now - timedelta(days=7)

    last_7 = route_df[route_df["timestamp"] >= last_start]
    prev_7 = route_df[(route_df["timestamp"] >= prev_start) & (route_df["timestamp"] < prev_end)]

    if last_7.empty or prev_7.empty:
        return "stable"

    last_avg = float(last_7["response_time_ms"].mean())
    prev_avg = float(prev_7["response_time_ms"].mean())
    if last_avg > prev_avg * 1.15:
        return "degrading"
    if last_avg < prev_avg * 0.85:
        return "improving"
    return "stable"


def _most_common_method(route_df: pd.DataFrame) -> str | None:
    if route_df.empty:
        return None
    modes = route_df["method"].mode()
    return str(modes.iloc[0]) if not modes.empty else None


def _build_route_analytics(route_df: pd.DataFrame, route: str, now: datetime) -> RouteAnalytics:
    total = len(route_df)
    errors = int((route_df["status_code"] >= 400).sum())
    error_rate = round((errors / total) * 100.0, 2) if total else 0.0

    lat = route_df["response_time_ms"]
    avg_lat = round(float(lat.mean()), 2) if total else 0.0
    p95 = round(float(lat.quantile(0.95)), 2) if total else 0.0
    p99 = round(float(lat.quantile(0.99)), 2) if total else 0.0
    min_lat = round(float(lat.min()), 2) if total else 0.0
    max_lat = round(float(lat.max()), 2) if total else 0.0
    avg_payload = round(float(route_df["payload_size_bytes"].mean()), 2) if total else 0.0

    score = _instability_score(error_rate, avg_lat, p95)
    suggest = _suggestion(error_rate, avg_lat, p95, avg_payload)
    trend = _trend_for_route(route_df, now)

    return RouteAnalytics(
        route=route,
        method=_most_common_method(route_df),
        total_requests=total,
        avg_latency_ms=avg_lat,
        p95_latency_ms=p95,
        p99_latency_ms=p99,
        min_latency_ms=min_lat,
        max_latency_ms=max_lat,
        error_rate_percent=error_rate,
        avg_payload_bytes=avg_payload,
        instability_score=score,
        suggestion=suggest,
        trend=trend,
    )


def _hourly_breakdown(route_df: pd.DataFrame) -> dict[str, float]:
    if route_df.empty:
        return {str(h): 0.0 for h in range(24)}
    grouped = route_df.groupby(route_df["timestamp"].dt.hour)["response_time_ms"].mean()
    return {str(h): round(float(grouped.get(h, 0.0)), 2) for h in range(24)}


def _daily_breakdown(route_df: pd.DataFrame, now: datetime) -> dict[str, float]:
    if route_df.empty:
        return {}
    start = now - timedelta(days=30)
    window = route_df[route_df["timestamp"] >= start]
    if window.empty:
        return {}
    daily = window.groupby(window["timestamp"].dt.strftime("%Y-%m-%d"))["response_time_ms"].mean()
    return {str(day): round(float(val), 2) for day, val in daily.items()}


def _status_distribution(route_df: pd.DataFrame) -> dict[str, int]:
    if route_df.empty:
        return {}
    counts = route_df["status_code"].astype(str).value_counts()
    return {str(k): int(v) for k, v in counts.items()}


def _method_breakdown(route_df: pd.DataFrame) -> dict[str, int]:
    if route_df.empty:
        return {}
    counts = route_df["method"].value_counts()
    return {str(k): int(v) for k, v in counts.items()}


@router.get(
    "/summary",
    response_model=list[RouteAnalytics],
    summary="Per-Route Analytics Summary",
    description=(
        "Returns aggregated analytics for **every API route** the authenticated user "
        "has uploaded logs for, sorted alphabetically.\n\n"
        "Each entry includes:\n"
        "- Average, P95, P99, min and max latency (ms)\n"
        "- Error rate percentage (status >= 400)\n"
        "- Instability score (0–10 composite metric)\n"
        "- Performance trend: `improving`, `stable`, or `degrading` (vs prior 7 days)\n"
        "- Actionable suggestion string\n\n"
        "Returns an empty list if no logs have been uploaded yet."
    ),
    responses={
        200: {"description": "List of per-route analytics objects, sorted by route path"},
        401: {"description": "Missing or invalid Bearer token"},
    },
)
async def analytics_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    df = await _fetch_user_logs_df(db, current_user.id)
    if df.empty:
        return []

    now = _now_utc()
    results: list[RouteAnalytics] = []
    for route, group in df.groupby("route", sort=True):
        results.append(_build_route_analytics(group, str(route), now))

    results.sort(key=lambda r: r.route)
    return results


@router.get(
    "/route/{route_name:path}",
    response_model=RouteDetail,
    summary="Detailed Analytics for a Single Route",
    description=(
        "Returns deep analytics for a **single API route**, identified by its URL path.\n\n"
        "URL-encode the route path when calling: e.g. `/analytics/route/%2Fapi%2Fpayments` "
        "for route `/api/payments`.\n\n"
        "In addition to the standard RouteAnalytics fields, this endpoint returns:\n"
        "- `hourly_breakdown` — average latency per hour of day (0–23)\n"
        "- `daily_breakdown` — average latency per calendar day (last 30 days)\n"
        "- `status_distribution` — count of each HTTP status code\n"
        "- `method_breakdown` — count of each HTTP method (GET/POST/etc.)"
    ),
    responses={
        200: {"description": "Detailed analytics object including breakdowns"},
        401: {"description": "Missing or invalid Bearer token"},
        404: {"description": "No data found for the specified route"},
    },
)
async def analytics_route_detail(
    route_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    decoded_route = unquote(route_name)
    if not decoded_route.startswith("/"):
        decoded_route = f"/{decoded_route.lstrip('/')}"

    df = await _fetch_user_logs_df(db, current_user.id)
    route_df = df[df["route"] == decoded_route]
    if route_df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for route: {decoded_route}",
        )

    now = _now_utc()
    base = _build_route_analytics(route_df, decoded_route, now)
    return RouteDetail(
        **base.model_dump(),
        hourly_breakdown=_hourly_breakdown(route_df),
        daily_breakdown=_daily_breakdown(route_df, now),
        status_distribution=_status_distribution(route_df),
        method_breakdown=_method_breakdown(route_df),
    )


@router.get(
    "/overview",
    response_model=OverviewStats,
    summary="Fleet-Wide Overview Statistics",
    description=(
        "Returns a single aggregated summary across **all routes** for the authenticated user.\n\n"
        "Useful for dashboard header cards. Includes:\n"
        "- `total_requests_all` — total log entries across all routes\n"
        "- `overall_error_rate` — fleet-wide error percentage\n"
        "- `slowest_route` — route with the highest average latency\n"
        "- `most_unstable_route` — route with the highest instability score\n"
        "- `healthiest_route` — route with the lowest instability score\n"
        "- `requests_last_24h` — request count in the trailing 24-hour window\n"
        "- `avg_latency_all` — mean latency across all routes and requests"
    ),
    responses={
        200: {"description": "Aggregated fleet overview stats"},
        401: {"description": "Missing or invalid Bearer token"},
    },
)
async def analytics_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    df = await _fetch_user_logs_df(db, current_user.id)
    now = _now_utc()

    if df.empty:
        return OverviewStats(
            total_requests_all=0,
            overall_error_rate=0.0,
            slowest_route=None,
            most_unstable_route=None,
            healthiest_route=None,
            total_routes=0,
            requests_last_24h=0,
            avg_latency_all=0.0,
        )

    total = len(df)
    errors = int((df["status_code"] >= 400).sum())
    overall_error = round((errors / total) * 100.0, 2) if total else 0.0
    last_24h = int((df["timestamp"] >= now - timedelta(hours=24)).sum())
    avg_all = round(float(df["response_time_ms"].mean()), 2)

    summaries = [
        _build_route_analytics(group, str(route), now) for route, group in df.groupby("route")
    ]

    slowest = max(summaries, key=lambda s: s.avg_latency_ms)
    most_unstable = max(summaries, key=lambda s: s.instability_score)
    healthiest = min(summaries, key=lambda s: s.instability_score)

    return OverviewStats(
        total_requests_all=total,
        overall_error_rate=overall_error,
        slowest_route=slowest.route,
        most_unstable_route=most_unstable.route,
        healthiest_route=healthiest.route,
        total_routes=len(summaries),
        requests_last_24h=last_24h,
        avg_latency_all=avg_all,
    )
