from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from database import get_db
from models import User
from routes.analytics import _now_utc
from services.prediction_service import calculate_risk_level, predict_route_latency
from services.sql_aggregators import fetch_prediction_stats
from core.logger import get_logger

router = APIRouter()
logger = get_logger("predictions_router")


class PredictionResponse(BaseModel):
    route: str
    predicted_latency: float
    risk_level: str
    confidence_score: float

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "route": "/api/payments",
                    "predicted_latency": 1540.2,
                    "risk_level": "CRITICAL",
                    "confidence_score": 0.85
                }
            ]
        }
    }


def _get_risk_weight(risk_level: str) -> int:
    """Helper to sort risk levels."""
    weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    return weights.get(risk_level, 0)


@router.get(
    "/routes",
    response_model=List[PredictionResponse],
    summary="Predict Latency & Risk for Routes",
    description=(
        "Uses the trained RandomForest model to predict the **future latency** and "
        "assign a **risk level** for each API route.\n\n"
        "The model is invoked with the **current time context** (`hour_of_day`, `day_of_week`) "
        "combined with per-route historical statistics fetched via a single PostgreSQL "
        "`GROUP BY` aggregation.\n\n"
        "**Risk level thresholds:**\n"
        "| Level | Condition |\n"
        "|---|---|\n"
        "| `LOW` | Predicted latency < 500ms |\n"
        "| `MEDIUM` | Predicted latency 500–1000ms |\n"
        "| `HIGH` | Predicted latency 1000–2000ms |\n"
        "| `CRITICAL` | Latency > 2000ms **or** error rate > 20% |\n\n"
        "**Prerequisite:** The ML model must be trained first by running `python ml/train.py`. "
        "Returns `503` if the model file is missing.\n\n"
        "Pass `?route=%2Fapi%2Fpayments` to predict a single route only."
    ),
    responses={
        200: {"description": "List of predictions ordered by route name"},
        401: {"description": "Missing or invalid Bearer token"},
        404: {"description": "No historical data found, or specified route not in data"},
        503: {"description": "ML model not trained yet — run ml/train.py first"},
    },
)
async def predict_routes(
    route: Optional[str] = Query(None, description="URL-encoded route path to filter (e.g. %2Fapi%2Fpayments). Omit to predict all routes."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Predicts latency and risk level for a specific route, or all routes if none specified.
    Uses the current time context for hour_of_day and day_of_week.
    """
    stats_map = await fetch_prediction_stats(db, current_user.id)
    if not stats_map:
        logger.warning(
            "Prediction requested but no historical data found",
            extra={"structured_data": {"user_id": current_user.id}}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No historical data found to make predictions."
        )

    now = _now_utc()
    hour_of_day = now.hour
    day_of_week = now.weekday()

    # Filter if specific route requested
    if route:
        routes_to_process = [route] if route in stats_map else []
    else:
        routes_to_process = list(stats_map.keys())

    predictions = []
    
    for r in routes_to_process:
        analytics = stats_map[r]
        
        # Prepare features for the ML model
        features = {
            "route": r,
            "method": "GET", # We simplify to GET as method doesn't heavily affect latency in our mock
            "status_code": 200,
            "payload_size_bytes": analytics["avg_payload_bytes"],
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "hist_avg_latency": analytics["avg_latency_ms"],
            "instability_score": analytics["instability_score"]
        }
        
        try:
            predicted_lat = predict_route_latency(features)
        except ValueError as e:
            # Catch "Model not found" errors
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail=str(e)
            )

        risk = calculate_risk_level(predicted_lat, analytics["error_rate_percent"])
        
        # Confidence score could be based on data volume
        confidence = min(0.99, 0.50 + (analytics["total_requests"] / 1000.0))
        
        predictions.append(
            PredictionResponse(
                route=r,
                predicted_latency=round(predicted_lat, 2),
                risk_level=risk,
                confidence_score=round(confidence, 2)
            )
        )

    if not predictions and route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route} not found in historical data."
        )

    logger.info(
        "Generated predictions successfully",
        extra={"structured_data": {
            "user_id": current_user.id,
            "routes_predicted": len(predictions)
        }}
    )

    return predictions


@router.get(
    "/top-risks",
    response_model=List[PredictionResponse],
    summary="Top-N Highest Risk Routes",
    description=(
        "Returns the top `limit` API routes ranked by **risk severity** (CRITICAL → HIGH → MEDIUM → LOW), "
        "with ties broken by predicted latency (descending).\n\n"
        "This endpoint is designed for **dashboard risk cards** — it surfaces the routes most likely "
        "to impact users right now, factoring in both the ML latency prediction and the historical "
        "error rate.\n\n"
        "Internally calls `/routes` with all routes, then sorts and truncates the result.\n\n"
        "**Prerequisite:** ML model must be trained (`python ml/train.py`)."
    ),
    responses={
        200: {"description": "Top-N routes sorted by risk level and predicted latency"},
        401: {"description": "Missing or invalid Bearer token"},
        404: {"description": "No historical data found — upload logs first"},
        503: {"description": "ML model not trained yet — run ml/train.py first"},
    },
)
async def get_top_risks(
    limit: int = Query(5, ge=1, le=50, description="Number of top-risk routes to return (1–50, default 5)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the highest-risk routes sorted in descending order of risk and latency.
    Suitable for dashboard risk cards and rankings.
    """
    # Reuse the logic from /routes to get all predictions
    predictions = await predict_routes(route=None, current_user=current_user, db=db)
    
    # Sort primarily by Risk Level (CRITICAL -> LOW) and secondarily by predicted latency
    predictions.sort(
        key=lambda x: (_get_risk_weight(x.risk_level), x.predicted_latency), 
        reverse=True
    )
    
    return predictions[:limit]
