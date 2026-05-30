from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class FailedRowDetail(BaseModel):
    row: int
    reason: str


class UploadResponse(BaseModel):
    message: str
    total_rows: int
    inserted_rows: int
    failed_rows: int
    failed_details: list[FailedRowDetail]
    routes_detected: list[str]
    upload_id: str


class UploadHistoryItem(BaseModel):
    upload_id: str
    filename: str
    total_rows: int
    inserted_rows: int
    failed_rows: int
    uploaded_at: datetime


class RouteAnalytics(BaseModel):
    route: str
    method: str | None = None
    total_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    error_rate_percent: float
    avg_payload_bytes: float
    instability_score: float
    suggestion: str
    trend: str


class RouteDetail(RouteAnalytics):
    hourly_breakdown: dict[str, float]
    daily_breakdown: dict[str, float]
    status_distribution: dict[str, int]
    method_breakdown: dict[str, int]


class OverviewStats(BaseModel):
    total_requests_all: int
    overall_error_rate: float
    slowest_route: str | None
    most_unstable_route: str | None
    healthiest_route: str | None
    total_routes: int
    requests_last_24h: int
    avg_latency_all: float
