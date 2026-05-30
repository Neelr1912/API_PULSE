from pathlib import Path
from typing import Any, Dict

import joblib
import pandas as pd

MODELS_DIR = Path(__file__).resolve().parent.parent / "ml" / "models"
MODEL_PATH = MODELS_DIR / "rf_latency_model.joblib"

# Cache the loaded model
_model_pipeline = None


def load_model():
    """Loads the ML pipeline from disk if not already loaded."""
    global _model_pipeline
    if _model_pipeline is None:
        if not MODEL_PATH.exists():
            return None
        try:
            _model_pipeline = joblib.load(MODEL_PATH)
        except Exception as e:
            raise ValueError(f"Failed to load model file. It may be corrupted: {e}")
    return _model_pipeline


def calculate_risk_level(predicted_latency: float, failure_rate_percent: float) -> str:
    """
    Categorizes the risk level based on latency and failure rate.
    
    Risk Levels:
    - LOW: latency < 500ms
    - MEDIUM: latency 500-1000ms
    - HIGH: latency 1000-2000ms
    - CRITICAL: latency > 2000ms OR failure rate > 20%
    """
    if failure_rate_percent > 20.0 or predicted_latency > 2000.0:
        return "CRITICAL"
    elif predicted_latency > 1000.0:
        return "HIGH"
    elif predicted_latency > 500.0:
        return "MEDIUM"
    else:
        return "LOW"


def predict_route_latency(features: Dict[str, Any]) -> float:
    """
    Predicts the response time latency given a dictionary of features.
    
    Expected features keys:
    - route (str)
    - method (str)
    - status_code (int)
    - payload_size_bytes (float)
    - hour_of_day (int)
    - day_of_week (int)
    - hist_avg_latency (float)
    - instability_score (float)
    """
    model = load_model()
    if not model:
        raise ValueError("Model not found. Please train the model first.")

    # Model expects a DataFrame
    df_features = pd.DataFrame([features])
    
    # Predict returns an array, we extract the first element
    predicted_latency = model.predict(df_features)[0]
    
    return float(predicted_latency)
