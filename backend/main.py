import asyncio
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


async def _auto_train():
    """Train the ML model on startup if the model file is missing."""
    if NUMPY_MODEL_PATH.exists():
        logger.info("ML model found — skipping auto-train.")
        return
    logger.warning("ML model not found — running auto-train on startup...")
    try:
        # train_models() is synchronous (uses asyncio.run internally),
        # so we run it in a thread to avoid blocking the event loop.
        from ml.train import train_models
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, train_models)
        if NUMPY_MODEL_PATH.exists():
            logger.info("Auto-train complete — model ready.")
        else:
            logger.warning("Auto-train ran but model file still missing (no data in DB?).")
    except Exception as e:
        logger.error(f"Auto-train failed: {e}. Predictions will return 503 until model is trained.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: auto-train model if missing, dispose DB pool on shutdown."""
    await _auto_train()
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
    return {"status": "ok", "service": "api-pulse"}


@app.get("/")
async def root():
    return {
        "message": "API-Pulse backend is running",
        "docs": "/docs",
        "health": "/health",
    }
