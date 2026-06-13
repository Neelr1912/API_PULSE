"""
Prediction service — uses the pure-numpy Random Forest for inference.

The sklearn pipeline is only needed at *training* time (ml/train.py).
At runtime we load the exported numpy model, which has zero sklearn DLL
dependencies and works regardless of Windows App Control policies.
"""

from typing import Any, Dict

from ml.numpy_forest import predict as numpy_predict


def calculate_risk_level(predicted_latency: float, failure_rate_percent: float) -> str:
    """
    Categorises the risk level based on latency and failure rate.

    Risk Levels:
    - LOW:      latency < 500ms
    - MEDIUM:   latency 500–1000ms
    - HIGH:     latency 1000–2000ms
    - CRITICAL: latency > 2000ms  OR  failure rate > 20%
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
    Predicts response-time latency given a dict of features.

    Expected keys:
    - route             (str)
    - method            (str)
    - status_code       (int)
    - payload_size_bytes (float)
    - hour_of_day       (int)
    - day_of_week       (int)
    - hist_avg_latency  (float)
    - instability_score (float)

    Raises ValueError if the model file is missing.
    """
    return numpy_predict(features)
