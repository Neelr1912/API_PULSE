import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from database import engine
from routes.analytics import router as analytics_router
from routes.predictions import router as predictions_router
from routes.upload import router as upload_router

load_dotenv()

logger = logging.getLogger("main")

# CORS origins: comma-separated in env, or default to local frontend
_cors_origins = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_origins.split(",") if o.strip()]

NUMPY_MODEL_PATH = Path(__file__).parent / "ml" / "models" / "rf_numpy_model.joblib"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: log model status on startup, dispose DB pool on shutdown."""
    if NUMPY_MODEL_PATH.exists():
        logger.info("ML model found and ready.")
    else:
        logger.warning(
            "ML model not found. Predictions will return 503 until the model is trained. "
            "Run: python ml/train.py"
        )
    yield
    await engine.dispose()


app = FastAPI(
    title="API-Pulse Predictive Engine",
    description=(
        "Smart Backend Route Failure & Latency Predictor API.\n\n"
        "Provides endpoints for CSV log ingestion, analytics aggregation, "
        "and Machine Learning based latency and risk-level predictions."
    ),
    version="1.0.0",
    contact={
        "name": "API-Pulse Developer",
        "url": "https://github.com/yourusername/api-pulse",
    },
    lifespan=lifespan,
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(upload_router, prefix="/upload", tags=["Upload"])
app.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
app.include_router(predictions_router, prefix="/api/predict", tags=["Predictions"])


@app.get("/health")
async def health_check():
    """Liveness probe for deployment and local dev."""
    model_path = Path(__file__).parent / "ml" / "models" / "rf_numpy_model.joblib"
    return {
        "status": "ok",
        "service": "api-pulse",
        "model_exists": model_path.exists(),
        "model_path": str(model_path),
        "model_size_bytes": model_path.stat().st_size if model_path.exists() else 0,
    }


@app.get("/")
async def root():
    return {
        "message": "API-Pulse backend is running",
        "docs": "/docs",
        "health": "/health",
    }
