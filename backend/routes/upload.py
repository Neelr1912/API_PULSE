import io
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from database import get_db
from models import APILog, UploadHistory, User
from schemas import FailedRowDetail, UploadHistoryItem, UploadResponse
from core.logger import get_logger

router = APIRouter()
logger = get_logger("upload_router")

REQUIRED_COLUMNS = [
    "route",
    "method",
    "status_code",
    "response_time_ms",
    "payload_size_bytes",
    "timestamp",
]
ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


def _parse_timestamp(value) -> datetime | None:
    try:
        ts = pd.to_datetime(value, utc=True)
        if pd.isna(ts):
            return None
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.to_pydatetime()
    except (TypeError, ValueError):
        return None


def _validate_row(row_num: int, row: pd.Series) -> tuple[dict | None, FailedRowDetail | None]:
    """Validate a single CSV row; return insert dict or failure detail."""
    method = str(row.get("method", "")).strip().upper()
    if method not in ALLOWED_METHODS:
        return None, FailedRowDetail(row=row_num, reason=f"Invalid method: {method or 'empty'}")

    try:
        status_code = int(row["status_code"])
    except (TypeError, ValueError):
        return None, FailedRowDetail(
            row=row_num,
            reason=f"Invalid status_code: {row.get('status_code')}",
        )
    if status_code < 100 or status_code > 599:
        return None, FailedRowDetail(row=row_num, reason=f"Invalid status_code: {status_code}")

    try:
        response_time_ms = float(row["response_time_ms"])
    except (TypeError, ValueError):
        return None, FailedRowDetail(
            row=row_num,
            reason=f"Invalid response_time_ms: {row.get('response_time_ms')}",
        )
    if response_time_ms <= 0:
        return None, FailedRowDetail(
            row=row_num,
            reason=f"response_time_ms must be positive: {response_time_ms}",
        )

    try:
        payload_size_bytes = float(row["payload_size_bytes"])
    except (TypeError, ValueError):
        return None, FailedRowDetail(
            row=row_num,
            reason=f"Invalid payload_size_bytes: {row.get('payload_size_bytes')}",
        )
    if payload_size_bytes <= 0:
        return None, FailedRowDetail(
            row=row_num,
            reason=f"payload_size_bytes must be positive: {payload_size_bytes}",
        )

    route = str(row.get("route", "")).strip()
    if not route:
        return None, FailedRowDetail(row=row_num, reason="Route is required")

    ts = _parse_timestamp(row["timestamp"])
    if ts is None:
        return None, FailedRowDetail(
            row=row_num,
            reason=f"Invalid timestamp: {row.get('timestamp')}",
        )

    return {
        "route": route,
        "method": method,
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "payload_size_bytes": payload_size_bytes,
        "timestamp": ts,
    }, None


@router.post(
    "/csv",
    response_model=UploadResponse,
    summary="Upload API Log CSV",
    description=(
        "Ingests a CSV file of historical API log data for the authenticated user.\n\n"
        "**Required CSV columns** (case-insensitive, order doesn't matter):\n"
        "- `route` — API path string (e.g. `/api/payments`)\n"
        "- `method` — HTTP method: GET, POST, PUT, DELETE, or PATCH\n"
        "- `status_code` — Integer HTTP status code (100–599)\n"
        "- `response_time_ms` — Response duration in milliseconds (must be > 0)\n"
        "- `payload_size_bytes` — Payload size in bytes (must be > 0)\n"
        "- `timestamp` — ISO-8601 or parseable datetime string\n\n"
        "Each row is validated individually. Invalid rows are reported in `failed_details` "
        "with the exact row number and reason — the valid rows are still inserted.\n\n"
        "The response includes `upload_id` (UUID) which groups this batch in the database."
    ),
    responses={
        200: {"description": "Upload complete — includes inserted/failed counts and detected routes"},
        400: {"description": "File is not a .csv, cannot be parsed, or missing required columns"},
        401: {"description": "Missing or invalid Bearer token"},
    },
)
async def upload_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        logger.warning(
            "Upload rejected: Invalid file extension",
            extra={"structured_data": {"user_id": current_user.id, "filename": filename}}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files accepted",
        )

    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read CSV file: {exc}",
        ) from exc

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required columns: {', '.join(missing)}",
        )

    upload_id = str(uuid4())
    total_rows = len(df)
    valid_rows: list[dict] = []
    failed_details: list[FailedRowDetail] = []

    # Row numbers are 1-based in the file (header is row 0; first data row is 2 in Excel terms)
    for offset, (_, row) in enumerate(df.iterrows()):
        row_num = offset + 2
        parsed, failure = _validate_row(row_num, row)
        if failure:
            failed_details.append(failure)
            continue
        parsed["user_id"] = current_user.id
        parsed["upload_id"] = upload_id
        valid_rows.append(parsed)

    if valid_rows:
        await db.execute(insert(APILog), valid_rows)

    routes_detected = sorted({r["route"] for r in valid_rows})

    history = UploadHistory(
        user_id=current_user.id,
        upload_id=upload_id,
        filename=filename,
        total_rows=total_rows,
        inserted_rows=len(valid_rows),
        failed_rows=len(failed_details),
    )
    db.add(history)
    await db.flush()

    logger.info(
        "CSV Upload complete",
        extra={"structured_data": {
            "user_id": current_user.id,
            "upload_id": upload_id,
            "filename": filename,
            "inserted_rows": len(valid_rows),
            "failed_rows": len(failed_details)
        }}
    )

    return UploadResponse(
        message="Upload successful",
        total_rows=total_rows,
        inserted_rows=len(valid_rows),
        failed_rows=len(failed_details),
        failed_details=failed_details,
        routes_detected=routes_detected,
        upload_id=upload_id,
    )


@router.get(
    "/history",
    response_model=list[UploadHistoryItem],
    summary="Upload History",
    description=(
        "Returns the list of all previous CSV uploads for the authenticated user, "
        "ordered by upload time descending (most recent first).\n\n"
        "Each item includes the original filename, `upload_id`, row counts "
        "(total / inserted / failed), and the UTC timestamp of the upload."
    ),
    responses={
        200: {"description": "List of past uploads ordered by most recent first"},
        401: {"description": "Missing or invalid Bearer token"},
    },
)
async def upload_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadHistory)
        .where(UploadHistory.user_id == current_user.id)
        .order_by(UploadHistory.uploaded_at.desc())
    )
    rows = result.scalars().all()
    return [
        UploadHistoryItem(
            upload_id=h.upload_id,
            filename=h.filename,
            total_rows=h.total_rows,
            inserted_rows=h.inserted_rows,
            failed_rows=h.failed_rows,
            uploaded_at=h.uploaded_at,
        )
        for h in rows
    ]
