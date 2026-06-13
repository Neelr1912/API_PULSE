import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path so we can import from local modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import select

from ml.numpy_forest import export_sklearn_forest, save_numpy_model
from database import AsyncSessionLocal
from models import APILog
from core.logger import get_logger

logger = get_logger("ml_train")

load_dotenv()

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def compute_instability_score(error_rate_percent: float, avg_latency_ms: float, p95_latency_ms: float) -> float:
    """Same instability logic used in analytics.py"""
    error_component = min(error_rate_percent / 100.0, 1.0) * 4.0
    latency_component = min(avg_latency_ms / 2000.0, 1.0) * 3.0
    tail_component = min(p95_latency_ms / 4000.0, 1.0) * 3.0
    return round(min(10.0, error_component + latency_component + tail_component), 2)


async def fetch_data() -> pd.DataFrame:
    """Fetch all API logs from PostgreSQL."""
    from database import DATABASE_URL
    import urllib.parse
    
    # Safely parse the URI to print only the host without credentials
    parsed_url = urllib.parse.urlparse(DATABASE_URL)
    safe_host = parsed_url.hostname or "unknown_host"
    
    logger.info("Fetching data from database", extra={"structured_data": {"host": safe_host, "table": APILog.__tablename__}})
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(APILog))
        rows = result.scalars().all()

        logger.info("Query complete", extra={"structured_data": {"total_records": len(rows)}})

        if not rows:
            return pd.DataFrame()

        data = [
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
        return pd.DataFrame(data)


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer features as specified."""
    # 1. Clean data: Handle null values and convert timezone
    df = df.dropna(subset=["route", "method", "status_code", "response_time_ms", "timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # 2. Extract time features
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek

    # 3. Calculate historical features & instability score per route
    route_stats = []
    for route, group in df.groupby("route"):
        total = len(group)
        errors = (group["status_code"] >= 400).sum()
        error_rate = (errors / total) * 100.0 if total > 0 else 0.0
        
        avg_lat = float(group["response_time_ms"].mean())
        p95_lat = float(group["response_time_ms"].quantile(0.95)) if total > 0 else avg_lat
        
        score = compute_instability_score(error_rate, avg_lat, p95_lat)
        
        route_stats.append({
            "route": route,
            "hist_avg_latency": avg_lat,
            "instability_score": score
        })
        
    stats_df = pd.DataFrame(route_stats)
    
    # Merge historical stats back into main dataframe
    df = df.merge(stats_df, on="route", how="left")
    
    # 4. Handle outliers (remove response times > 99th percentile globally)
    p99_global = df["response_time_ms"].quantile(0.99)
    df = df[df["response_time_ms"] <= p99_global]
    
    return df


def train_models():
    logger.info("Starting ML pipeline")
    df = asyncio.run(fetch_data())
    
    if df.empty:
        logger.warning("No data available in the database to train the model")
        return

    logger.info("Data fetched successfully", extra={"structured_data": {"shape": list(df.shape)}})
    df = feature_engineering(df)
    
    # Define features and target
    features = [
        "route", "method", "status_code", "payload_size_bytes",
        "hour_of_day", "day_of_week", "hist_avg_latency", "instability_score"
    ]
    target = "response_time_ms"

    X = df[features]
    y = df[target]

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"Training dataset size (total): {len(X)}")
    print(f"Train split size: {len(X_train)}")
    print(f"Test split size: {len(X_test)}")

    # Preprocessor for categorical and numerical data
    categorical_features = ["route", "method"]
    numerical_features = [
        "status_code", "payload_size_bytes", "hour_of_day", 
        "day_of_week", "hist_avg_latency", "instability_score"
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numerical_features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ]
    )

    # 1. Baseline Model: Linear Regression
    lr_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", LinearRegression())
    ])
    
    print("Training Linear Regression Baseline...")
    lr_pipeline.fit(X_train, y_train)
    lr_preds = lr_pipeline.predict(X_test)
    
    print("\n--- Linear Regression Evaluation ---")
    print(f"MAE:  {mean_absolute_error(y_test, lr_preds):.2f}")
    print(f"RMSE: {np.sqrt(mean_squared_error(y_test, lr_preds)):.2f}")
    print(f"R2:   {r2_score(y_test, lr_preds):.4f}")

    # 2. Primary Model: Random Forest Regressor
    rf_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1))
    ])
    
    print("\nTraining Random Forest Primary Model...")
    rf_pipeline.fit(X_train, y_train)
    rf_preds = rf_pipeline.predict(X_test)
    
    print("\n--- Random Forest Evaluation ---")
    print(f"MAE:  {mean_absolute_error(y_test, rf_preds):.2f}")
    print(f"RMSE: {np.sqrt(mean_squared_error(y_test, rf_preds)):.2f}")
    print(f"R2:   {r2_score(y_test, rf_preds):.4f}")

    # ── Model Persistence ─────────────────────────────────────────────────────
    # 1. Save the full sklearn pipeline (useful for retraining / inspection)
    model_path = MODELS_DIR / "rf_latency_model.joblib"
    joblib.dump(rf_pipeline, model_path)

    # 2. Export a pure-numpy version so the FastAPI server can load the model
    #    without needing sklearn DLLs (works around Windows App Control blocks).
    print("\nExporting numpy model for DLL-free inference...")
    numpy_model = export_sklearn_forest(rf_pipeline, features)
    save_numpy_model(numpy_model)
    print(f"Numpy model saved → {MODELS_DIR / 'rf_numpy_model.joblib'}")

    logger.info("Training complete and model saved", extra={"structured_data": {
        "model_path": str(model_path),
        "rf_r2_score": r2_score(y_test, rf_preds),
        "lr_r2_score": r2_score(y_test, lr_preds)
    }})


if __name__ == "__main__":
    train_models()
