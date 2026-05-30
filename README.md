# ⚡ API-Pulse – Smart Backend Route Failure & Latency Predictor

> A proactive, ML-powered observability platform that ingests API logs, computes real-time analytics, and predicts route failures before your users notice.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.4+-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-0db7ed?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 🧭 Project Overview

**The Problem:** Traditional API monitoring is purely reactive. By the time an alert fires for a degraded endpoint, users are already experiencing timeouts or 500 errors. 

**Why it matters:** In modern microservice architectures, a single bottlenecked route can cascade into full system failures.

**The Solution:** API-Pulse shifts from reactive alerting to **proactive prediction**. By ingesting historical API logs into PostgreSQL, it computes deep latency analytics and trains a Random Forest Machine Learning model. The system then dynamically predicts future latency and assigns risk levels to every route, allowing engineers to fix bottlenecks *before* they cause outages.

---

## ✨ Features

- **JWT Authentication:** Secure user registration and login with bcrypt password hashing.
- **CSV Upload & Validation:** Bulk ingestion pipeline for historical API logs with per-row Pydantic validation.
- **Analytics Dashboard Data:** Real-time generation of P95/P99 latency metrics and error rates.
- **Route Performance Monitoring:** Granular insights into individual endpoints, including hourly/daily breakdowns.
- **Instability Scoring:** Custom heuristic algorithm combining error rates and latency variance.
- **Trend Analysis:** Automated detection of whether a route is improving, stable, or degrading.
- **ML-Based Latency Prediction:** Uses a Random Forest Regressor to predict route response times based on temporal and historical features.
- **Risk Detection:** Classifies routes into `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` risk tiers.
- **Dockerized Deployment:** Fully containerized setup with Docker Compose for immediate spin-up.

---

## 🏗️ Architecture

```mermaid
graph TD
    User([User / Client])
    UploadLogs[CSV Upload / Logs]
    FastAPI[FastAPI Backend]
    PostgreSQL[(PostgreSQL - Supabase)]
    Analytics[Analytics Engine]
    MLModel[Random Forest ML Model]
    Predictions[Latency & Risk Predictions]

    User -->|Auth & Requests| FastAPI
    UploadLogs -->|Bulk Insert| FastAPI
    FastAPI -->|Write Logs| PostgreSQL
    PostgreSQL -->|SQL Aggregations| Analytics
    PostgreSQL -->|Training Data| MLModel
    Analytics -->|Feature Data| MLModel
    MLModel -->|Inference| Predictions
    Predictions -->|API Response| User
```

---

## 🛠 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI, Python 3.11 | High-performance async REST API |
| **Database** | PostgreSQL (Supabase) | Persistent storage & native SQL aggregation |
| **ORM** | SQLAlchemy 2.0 (Async) | Database interaction and migrations (Alembic) |
| **Machine Learning** | Scikit-Learn, Pandas | Random Forest training, data scaling |
| **Authentication** | Passlib, python-jose | Bcrypt hashing and JWT generation |
| **Containerization** | Docker, Docker Compose | Environment consistency and deployment |

---

## 🗄️ Database Schema

The core relational structure is optimized for fast insertion and heavy analytical querying:

- **`users`**: Manages authentication (`id`, `username`, `email`, `hashed_password`).
- **`upload_history`**: Tracks CSV bulk uploads and failure counts.
- **`api_logs`**: Massive table storing individual request events (`route`, `method`, `status_code`, `response_time_ms`, `timestamp`).
- **`predictions`**: Caches inference results for fast retrieval.

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/auth/register` | Register a new user |
| **POST** | `/auth/login` | Authenticate and retrieve JWT token |
| **POST** | `/upload/csv` | Bulk upload historical API logs |
| **GET** | `/upload/history` | Retrieve history of log uploads |
| **GET** | `/analytics/overview` | System-wide performance overview |
| **GET** | `/analytics/summary` | Comparative statistics across all routes |
| **GET** | `/analytics/route/{name}` | Deep-dive analytics for a specific route |
| **GET** | `/api/predict/routes` | Predict latency and assign risk for routes |
| **GET** | `/api/predict/top-risks` | Retrieve the highest-risk routes dynamically |

---

## 🤖 Machine Learning Workflow

API-Pulse utilizes a classic supervised learning pipeline to forecast degradation:

1. **Feature Engineering**: Extracts temporal context (`hour_of_day`, `day_of_week`) and computes historical baselines (average latency, instability score) via PostgreSQL native aggregations.
2. **Training**: Uses a `RandomForestRegressor` (Scikit-Learn) on historical data, applying `StandardScaler` to numerical inputs and `OneHotEncoder` to categorical inputs.
3. **Prediction**: At inference time, the model processes current temporal data against historical route signatures to estimate upcoming latency (in milliseconds).
4. **Risk Scoring**: Predicted latency is mapped against error-rate thresholds to classify the route as `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.

---

## 📸 Screenshots

| Login & Authentication | CSV Log Upload |
| :---: | :---: |
| *(Add Login Screenshot Here)* | *(Add Upload Screenshot Here)* |

| Real-Time Analytics | ML Predictions & Risk |
| :---: | :---: |
| *(Add Analytics Screenshot Here)* | *(Add Predictions Screenshot Here)* |

---

## 🚀 Installation Guide

### Prerequisites
- Python 3.11+
- PostgreSQL Database (Supabase recommended)
- Docker (optional but recommended)

### Option 1: Docker Setup (Recommended)
```bash
# Clone the repo
git clone https://github.com/yourusername/api-pulse.git
cd api-pulse

# Set up environment variables
cp .env.example backend/.env

# Build and start containers
docker-compose up -d --build

# Run database migrations
docker-compose exec backend alembic upgrade head
```

### Option 2: Local Setup
```bash
# Setup virtual environment
cd backend
python -m venv .venv

# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate 

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp ../.env.example .env

# Run migrations
alembic upgrade head

# Start the server
uvicorn main:app --reload --port 8080
```

### Environment Variables (`.env`)
```env
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
SECRET_KEY=your_super_secret_jwt_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
LOG_LEVEL=INFO
```

---

## 🎯 Resume-Worthy Achievements

- **End-to-End Pipeline**: Architected a complete data pipeline from raw CSV ingestion to ML inference within a single FastAPI application.
- **SQL Optimization**: Bypassed slow Pandas dataframe aggregations by writing native PostgreSQL `GROUP BY` and `percentile_cont` queries, improving prediction inference speed by ~10x.
- **Predictive Observability**: Designed a custom heuristic instability score combining error rates and variance to identify failing microservices proactively.

---

## 🔮 Future Scope

- **Grafana Integration**: Export metrics to Grafana dashboards for visual exploration.
- **Prometheus Integration**: Expose an `/metrics` endpoint for standard Prometheus scraping.
- **Real-Time Monitoring**: Transition from batch CSV uploads to real-time Kafka log streaming.
- **Alerting System**: Automated webhook integrations (Slack/PagerDuty) when a route hits `CRITICAL` status.
- **Advanced ML Models**: Experiment with LSTM or Transformer models for complex time-series anomaly detection.

---

## 🏷️ GitHub Topics
`fastapi` `machine-learning` `postgresql` `observability` `api-monitoring` `scikit-learn` `python` `docker` `predictive-analytics` `backend`

---
*Built with ❤️ for proactive engineering.*
