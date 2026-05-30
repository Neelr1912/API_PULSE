# API-Pulse — Architecture Documentation

## 1. System Flow

API-Pulse operates on a three-tier architecture. The **Client Layer** communicates exclusively via JWT-authenticated HTTP requests. The **Application Layer** (FastAPI) routes each request to the appropriate service. The **Data Layer** consists of PostgreSQL for persistence and a serialized Joblib model for ML inference.

```mermaid
graph TD
    subgraph "Client Layer"
        FE[Frontend Dashboard\nVanilla JS + HTML]
        CLI[API Client\ncurl / Postman / SDK]
    end

    subgraph "FastAPI Application Layer"
        direction TB
        MW[CORS Middleware\nJWT Validation]
        AR[Auth Router\nPOST /auth/register\nPOST /auth/login\nGET  /auth/me]
        UR[Upload Router\nPOST /upload/csv\nGET  /upload/history]
        ANR[Analytics Router\nGET /analytics/summary\nGET /analytics/overview\nGET /analytics/route/:name]
        PR[Prediction Router\nGET /api/predict/routes\nGET /api/predict/top-risks]
        LOG[Structured JSON Logger\ncore/logger.py]
    end

    subgraph "Data Layer"
        DB[(PostgreSQL\nSupabase\napi_logs · users\nupload_history · predictions)]
        AGG[SQL Aggregations\nGROUP BY + percentile_cont\nsql_aggregators.py]
        MDL[rf_latency_model.joblib\nRandomForest Pipeline\n100 estimators]
        TRAIN[ml/train.py\nOffline Training Script\nRuns manually or via cron]
    end

    FE & CLI --> MW
    MW --> AR & UR & ANR & PR
    AR --> DB
    UR -->|Async bulk INSERT| DB
    ANR -->|SELECT + Pandas groupby| DB
    PR -->|SQL GROUP BY aggregation| AGG
    AGG --> DB
    PR -->|joblib.load cached| MDL
    DB -->|Full dataset fetch| TRAIN
    TRAIN -->|Serializes pipeline| MDL
    AR & UR & ANR & PR --> LOG
```

---

## 2. Database Schema

```mermaid
erDiagram
    users {
        int     id              PK  "Primary key, auto-increment"
        varchar username        UK  "Max 64 chars, unique, indexed"
        varchar email           UK  "Max 255 chars, unique, indexed"
        varchar hashed_password     "bcrypt hash"
        timestamptz created_at      "Server default: now()"
    }

    upload_history {
        int     id          PK  "Primary key"
        int     user_id     FK  "CASCADE DELETE → users.id"
        varchar upload_id       "UUID v4, indexed"
        varchar filename        "Original CSV filename"
        int     total_rows      "Total rows in uploaded file"
        int     inserted_rows   "Successfully parsed + inserted"
        int     failed_rows     "Validation failures"
        timestamptz uploaded_at "Server default: now()"
    }

    api_logs {
        int     id                  PK  "Primary key, indexed"
        int     user_id             FK  "CASCADE DELETE → users.id, indexed"
        varchar upload_id               "UUID v4, indexed (batch grouping)"
        varchar route                   "API path e.g. /api/payments, indexed"
        varchar method                  "GET POST PUT DELETE PATCH"
        int     status_code             "HTTP status 100–599, indexed"
        float   response_time_ms        "Response duration in milliseconds"
        float   payload_size_bytes      "Request/response payload size"
        timestamptz timestamp           "Original log timestamp, indexed"
        timestamptz created_at          "DB insertion time, server default"
    }

    predictions {
        int     id                      PK  "Primary key"
        int     user_id                 FK  "CASCADE DELETE → users.id, indexed"
        varchar route                       "API path predicted"
        float   predicted_latency_ms        "ML model output in ms"
        float   failure_probability         "Computed failure probability"
        timestamptz generated_at            "Server default: now()"
    }

    users ||--o{ upload_history  : "owns"
    users ||--o{ api_logs        : "owns"
    users ||--o{ predictions     : "owns"
    upload_history }o--o{ api_logs : "groups (upload_id)"
```

### Key Indexes

| Table | Column(s) | Reason |
|---|---|---|
| `api_logs` | `(user_id)` | All analytics queries filter by user |
| `api_logs` | `(route)` | GROUP BY route in aggregations |
| `api_logs` | `(status_code)` | Error rate computation |
| `api_logs` | `(timestamp)` | Time-windowed queries (last 24h, 7d) |
| `users` | `(username)`, `(email)` | Uniqueness enforcement at DB level |

---

## 3. Prediction Workflow

```mermaid
sequenceDiagram
    participant Client
    participant PredictRouter
    participant SQLAggregator
    participant PostgreSQL
    participant PredictionService
    participant MLModel

    Client->>PredictRouter: GET /api/predict/top-risks\n(Bearer token)
    PredictRouter->>SQLAggregator: fetch_prediction_stats(user_id)

    SQLAggregator->>PostgreSQL: SELECT route,\nCOUNT(*), AVG(response_time_ms),\nAVG(payload_size_bytes),\npercentile_cont(0.95),\nSUM(CASE status >= 400...)\nGROUP BY route

    PostgreSQL-->>SQLAggregator: Aggregated rows (1 row per route)
    SQLAggregator-->>PredictRouter: stats_map {route → {avg_lat, error_rate, ...}}

    Note over PredictRouter: Adds time context:\nhour_of_day = now().hour\nday_of_week = now().weekday()

    loop For each route in stats_map
        PredictRouter->>PredictionService: predict_route_latency(feature_dict)
        PredictionService->>MLModel: model.predict(DataFrame)
        MLModel-->>PredictionService: predicted_latency_ms (float)
        PredictionService-->>PredictRouter: predicted_latency
        PredictRouter->>PredictRouter: calculate_risk_level(latency, error_rate)
    end

    PredictRouter->>PredictRouter: Sort by risk_weight + predicted_latency DESC
    PredictRouter-->>Client: Top-N PredictionResponse list
```

---

## 4. ML Training Pipeline

```mermaid
flowchart TD
    A[python ml/train.py] --> B[fetch_data\nasync SQLAlchemy query\nall api_logs for all users]
    B --> C{Rows found?}
    C -- No --> STOP[Log warning and exit]
    C -- Yes --> D[feature_engineering]

    D --> D1[Parse timestamps → UTC]
    D1 --> D2[Extract hour_of_day\nday_of_week]
    D2 --> D3[Per-route aggregation\nhist_avg_latency\ninstability_score]
    D3 --> D4[Merge stats back\nonto each row]
    D4 --> D5[Remove p99 outliers\nglobally]

    D5 --> E[Train/Test Split\n80% train · 20% test\nrandom_state=42]

    E --> F[ColumnTransformer Preprocessor]
    F --> F1[StandardScaler\nstatus_code · payload_size_bytes\nhour_of_day · day_of_week\nhist_avg_latency · instability_score]
    F --> F2[OneHotEncoder\nroute · method\nhandle_unknown=ignore]

    F1 & F2 --> G[Baseline Pipeline\nLinearRegression\nMAE · RMSE · R²]
    F1 & F2 --> H[Primary Pipeline\nRandomForestRegressor\nn_estimators=100\nn_jobs=-1]

    H --> I[Evaluate on test set\nMAE · RMSE · R²]
    I --> J[joblib.dump\nml/models/rf_latency_model.joblib]
    J --> K[Inference ready\n/api/predict/* endpoints]
```

---

## 5. PostgreSQL GROUP BY Optimization

### Problem

The initial analytics approach loaded **all** `api_logs` rows for a user into memory as a Pandas DataFrame, then computed aggregations in Python. For users with 100k+ rows, this caused:
- High memory pressure in the container
- 500–2000ms latency on prediction endpoints

### Solution: Native SQL Aggregation

The `services/sql_aggregators.py` module pushes all aggregation work directly into PostgreSQL using a single `GROUP BY` query:

```sql
SELECT
    route,
    COUNT(id)                                              AS total,
    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END)   AS errors,
    AVG(response_time_ms)                                  AS avg_lat,
    AVG(payload_size_bytes)                                AS avg_payload,
    percentile_cont(0.95) WITHIN GROUP
        (ORDER BY response_time_ms ASC)                    AS p95_lat
FROM api_logs
WHERE user_id = :user_id
GROUP BY route;
```

**Benefits:**
- PostgreSQL executes this in a single sequential scan with hash aggregation
- `percentile_cont` is a native ordered-set aggregate — far more efficient than fetching raw data and calling `DataFrame.quantile()`
- Returns **one row per route** regardless of dataset size
- Response time improvement: ~10× on datasets with 50k+ rows

---

## 6. Logging Architecture

Every request path emits structured JSON logs:

```json
{
  "timestamp": "2024-05-15T10:30:00.123456+00:00",
  "level": "INFO",
  "message": "CSV Upload complete",
  "service": "api-pulse",
  "version": "1.0.0",
  "module": "upload_router",
  "user_id": 42,
  "upload_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "filename": "api_logs_may.csv",
  "inserted_rows": 997,
  "failed_rows": 3
}
```

Configure via env vars:
- `LOG_LEVEL` — sets the minimum severity (default `INFO`)
- `LOG_FILE` — optional path; if set, logs are also written to a rotating file handler
