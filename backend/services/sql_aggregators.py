from typing import Any, Dict
from sqlalchemy import select, func, cast, Float, Integer
from sqlalchemy.sql.expression import case
from sqlalchemy.ext.asyncio import AsyncSession
from models import APILog
from routes.analytics import _instability_score

async def fetch_prediction_stats(db: AsyncSession, user_id: int) -> Dict[str, Dict[str, Any]]:
    """
    Fetches aggregated historical stats (avg latency, payload, error rate, p95 latency)
    directly from PostgreSQL, bypassing Pandas to save memory.
    """
    # PostgreSQL-specific percentile_cont
    p95_func = func.percentile_cont(0.95).within_group(APILog.response_time_ms.asc())
    
    stmt = select(
        APILog.route,
        func.count(APILog.id).label("total"),
        func.sum(case((APILog.status_code >= 400, 1), else_=0)).label("errors"),
        func.avg(APILog.response_time_ms).label("avg_lat"),
        func.avg(APILog.payload_size_bytes).label("avg_payload"),
        p95_func.label("p95_lat")
    ).where(APILog.user_id == user_id).group_by(APILog.route)

    result = await db.execute(stmt)
    rows = result.all()
    
    stats_map = {}
    for row in rows:
        total = int(row.total or 0)
        errors = int(row.errors or 0)
        error_rate = (errors / total) * 100.0 if total > 0 else 0.0
        avg_lat = float(row.avg_lat or 0.0)
        p95_lat = float(row.p95_lat or avg_lat)
        avg_payload = float(row.avg_payload or 0.0)
        
        score = _instability_score(error_rate, avg_lat, p95_lat)
        
        stats_map[row.route] = {
            "total_requests": total,
            "error_rate_percent": error_rate,
            "avg_latency_ms": avg_lat,
            "avg_payload_bytes": avg_payload,
            "instability_score": score
        }
        
    return stats_map
