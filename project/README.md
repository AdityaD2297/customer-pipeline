# Customer Data Pipeline

A three-service Docker data pipeline built for the Backend Developer Technical Assessment.

## Architecture

```
Flask Mock Server (port 5000)
        │
        │  JSON over HTTP (paginated)
        ▼
FastAPI Pipeline Service (port 8000)
        │
        │  SQLAlchemy upsert
        ▼
PostgreSQL (port 5432)
```

## Project Structure

```
project-root/
├── docker-compose.yml
├── README.md
├── mock-server/
│   ├── app.py                  # Flask REST API
│   ├── data/
│   │   └── customers.json      # 22 customer records
│   ├── Dockerfile
│   └── requirements.txt
└── pipeline-service/
    ├── main.py                 # FastAPI app & endpoints
    ├── database.py             # SQLAlchemy engine & session
    ├── models/
    │   └── customer.py         # Customer ORM model
    ├── services/
    │   └── ingestion.py        # Pagination fetch + upsert logic
    ├── Dockerfile
    └── requirements.txt
```

## Prerequisites

- Docker Desktop (running)
- Docker Compose v2+

## Quick Start

```bash
# Clone / unzip the project, then:
cd project-root

# Build and start all three services
docker-compose up -d --build

# Verify all containers are healthy
docker-compose ps
```

Wait ~15 seconds for all health-checks to pass, then run the tests below.

## API Reference

### Flask Mock Server — `http://localhost:5000`

| Method | Endpoint                    | Description                          |
|--------|-----------------------------|--------------------------------------|
| GET    | `/api/health`               | Health check                         |
| GET    | `/api/customers`            | Paginated list (`page`, `limit`)     |
| GET    | `/api/customers/{id}`       | Single customer or 404               |

### FastAPI Pipeline Service — `http://localhost:8000`

| Method | Endpoint                    | Description                          |
|--------|-----------------------------|--------------------------------------|
| GET    | `/api/health`               | Health check                         |
| POST   | `/api/ingest`               | Fetch all Flask data → upsert to DB  |
| GET    | `/api/customers`            | Paginated results from DB            |
| GET    | `/api/customers/{id}`       | Single customer from DB or 404       |
| GET    | `/docs`                     | Swagger UI (auto-generated)          |

## Testing

```bash
# 1. Health checks
curl http://localhost:5000/api/health
curl http://localhost:8000/api/health

# 2. Flask — paginated list
curl "http://localhost:5000/api/customers?page=1&limit=5"

# 3. Flask — single customer
curl http://localhost:5000/api/customers/CUST-001

# 4. Flask — 404
curl http://localhost:5000/api/customers/CUST-999

# 5. Ingest all data into PostgreSQL
curl -X POST http://localhost:8000/api/ingest

# 6. FastAPI — paginated results from DB
curl "http://localhost:8000/api/customers?page=1&limit=5"

# 7. FastAPI — single customer from DB
curl http://localhost:8000/api/customers/CUST-001

# 8. FastAPI — 404
curl http://localhost:8000/api/customers/CUST-999
```

## Design Decisions

### Flask Mock Server
- Customer data is loaded from `data/customers.json` on every request (no hardcoding).
- Pagination uses `page` + `limit` query params; the response includes `total`, `page`, and `limit` for easy client-side handling.
- Returns HTTP 404 with a JSON error body for unknown customer IDs.
- Served with **Gunicorn** (2 workers) for production-grade process management.

### FastAPI Pipeline Service
- **Auto-pagination**: the ingestion service fetches pages from Flask until `len(accumulated) >= total`, so it handles any dataset size without manual page counting.
- **Upsert logic**: uses PostgreSQL's `INSERT … ON CONFLICT DO UPDATE` (via SQLAlchemy's `pg_insert`) so repeated calls to `/api/ingest` are idempotent.
- **Schema auto-creation**: `init_db()` is called at startup via FastAPI's `lifespan` hook; no manual migrations needed for this assessment.
- **Type coercion**: dates (`date_of_birth`) and timestamps (`created_at`) in the JSON are parsed to proper Python/SQLAlchemy types before insertion.

### Docker Compose
- `postgres` exposes a `pg_isready` health-check; the other two services declare `condition: service_healthy` so start order is deterministic.
- `mock-server` also exposes a health-check so `pipeline-service` waits until Flask is actually serving requests before starting.
- A named volume (`pgdata`) persists database data across `docker-compose down` / `up` cycles.

## Stopping / Cleanup

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (wipes DB data)
docker-compose down -v
```
