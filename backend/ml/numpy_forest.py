"""
Pure-numpy Random Forest inference.

The sklearn RandomForest is trained once (requires system Python with sklearn).
train.py exports every tree's decision arrays + the preprocessing metadata
into a single .joblib file containing only Python dicts and numpy arrays.

This module loads that file and runs inference using only numpy — no sklearn
DLLs needed, so it works even when Windows App Control blocks sklearn.
"""

from __future__ import annotations

import numpy as np
import joblib
from pathlib import Path
from typing import Any

MODELS_DIR = Path(__file__).resolve().parent / "models"
NUMPY_MODEL_PATH = MODELS_DIR / "rf_numpy_model.joblib"

_cached_model: dict | None = None


# ── Serialisation helpers (called from train.py) ─────────────────────────────

def export_sklearn_forest(rf_pipeline, feature_names: list[str]) -> dict:
    """
    Extract everything needed for inference from a fitted sklearn Pipeline
    (ColumnTransformer → RandomForestRegressor) into plain Python/numpy data.
    """
    preprocessor = rf_pipeline.named_steps["preprocessor"]
    regressor    = rf_pipeline.named_steps["regressor"]

    # ── Numerical scaler ──────────────────────────────────────────────────────
    num_transformer  = preprocessor.named_transformers_["num"]
    scaler_mean      = num_transformer.mean_.copy()
    scaler_scale     = num_transformer.scale_.copy()

    # ── Categorical encoder ───────────────────────────────────────────────────
    cat_transformer  = preprocessor.named_transformers_["cat"]
    # categories_ is a list of arrays, one per categorical feature
    categories       = [arr.tolist() for arr in cat_transformer.categories_]

    # ── Column ordering (ColumnTransformer output order) ──────────────────────
    # "num" columns come first, then "cat" columns (sklearn default)
    num_feature_names = preprocessor.transformers_[0][2]   # e.g. ["status_code", ...]
    cat_feature_names = preprocessor.transformers_[1][2]   # e.g. ["route", "method"]

    # ── Tree arrays from every estimator ──────────────────────────────────────
    trees = []
    for estimator in regressor.estimators_:
        t = estimator.tree_
        trees.append({
            "children_left":  t.children_left.copy(),
            "children_right": t.children_right.copy(),
            "feature":        t.feature.copy(),
            "threshold":      t.threshold.copy(),
            "value":          t.value[:, 0, 0].copy(),  # shape (n_nodes,)
        })

    return {
        "feature_names":     feature_names,
        "num_feature_names": list(num_feature_names),
        "cat_feature_names": list(cat_feature_names),
        "scaler_mean":       scaler_mean,
        "scaler_scale":      scaler_scale,
        "categories":        categories,    # list[list[str]]
        "trees":             trees,
    }


def save_numpy_model(model_dict: dict) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_dict, NUMPY_MODEL_PATH)


# ── Inference helpers (called at runtime, numpy-only) ─────────────────────────

def _load_model() -> dict:
    global _cached_model
    if _cached_model is None:
        if not NUMPY_MODEL_PATH.exists():
            raise ValueError("Model not found. Please train the model first.")
        _cached_model = joblib.load(NUMPY_MODEL_PATH)
    return _cached_model


def _predict_single_tree(tree: dict, x: np.ndarray) -> float:
    """Walk one decision tree and return the leaf value."""
    node = 0
    cl   = tree["children_left"]
    cr   = tree["children_right"]
    feat = tree["feature"]
    thr  = tree["threshold"]
    val  = tree["value"]

    while cl[node] != -1:          # -1 == TREE_LEAF in sklearn
        if x[feat[node]] <= thr[node]:
            node = cl[node]
        else:
            node = cr[node]
    return float(val[node])


def _preprocess(features: dict, model: dict) -> np.ndarray:
    """
    Replicate ColumnTransformer(StandardScaler, OneHotEncoder) with numpy.
    Input : raw feature dict   (same keys as training)
    Output: 1-D float64 array  (same layout as sklearn's transform output)
    """
    # ── Numerical part ────────────────────────────────────────────────────────
    num_vals = np.array(
        [float(features[f]) for f in model["num_feature_names"]],
        dtype=np.float64,
    )
    num_scaled = (num_vals - model["scaler_mean"]) / model["scaler_scale"]

    # ── Categorical part (OHE, handle_unknown="ignore") ───────────────────────
    ohe_parts = []
    for i, col in enumerate(model["cat_feature_names"]):
        cats = model["categories"][i]      # list of known category strings
        val  = features[col]
        ohe  = np.zeros(len(cats), dtype=np.float64)
        if val in cats:
            ohe[cats.index(val)] = 1.0
        ohe_parts.append(ohe)

    cat_encoded = np.concatenate(ohe_parts) if ohe_parts else np.array([])

    return np.concatenate([num_scaled, cat_encoded])


def predict(features: dict) -> float:
    """
    Public inference function.
    features: dict with keys matching the training feature set.
    Returns predicted latency as float.
    """
    model   = _load_model()
    x       = _preprocess(features, model)
    preds   = [_predict_single_tree(tree, x) for tree in model["trees"]]
    return float(np.mean(preds))
