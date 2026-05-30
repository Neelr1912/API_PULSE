import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from database import engine
from routes.analytics import router as analytics_router
from routes.predictions import router as predictions_router
from routes.upload import router as upload_router

load_dotenv()

# CORS origins: comma-separated in env, or default to local frontend
_cors_origins = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_origins.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup/shutdown hooks (DB pool managed by engine)."""
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
