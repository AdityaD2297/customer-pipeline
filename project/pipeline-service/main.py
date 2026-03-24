import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, init_db
from models.customer import Customer
from services.ingestion import fetch_all_customers, upsert_customers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising database schema…")
    init_db()
    logger.info("Database ready.")
    yield


app = FastAPI(title="Customer Pipeline Service", version="1.0.0", lifespan=lifespan)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "pipeline-service"}


# ── Ingest ────────────────────────────────────────────────────────────────────

@app.post("/api/ingest")
def ingest(db: Session = Depends(get_db)):
    """Fetch all customers from the Flask mock server and upsert into PostgreSQL."""
    try:
        logger.info("Starting ingestion from mock server…")
        customers = fetch_all_customers()
        count = upsert_customers(db, customers)
        logger.info("Ingestion complete — %d records processed.", count)
        return {"status": "success", "records_processed": count}
    except Exception as exc:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=502, detail=f"Ingestion failed: {exc}") from exc


# ── Customers ─────────────────────────────────────────────────────────────────

@app.get("/api/customers")
def list_customers(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(10, ge=1, le=100, description="Records per page"),
    db: Session = Depends(get_db),
):
    total = db.query(Customer).count()
    offset = (page - 1) * limit
    rows = db.query(Customer).offset(offset).limit(limit).all()
    return {
        "data": [r.to_dict() for r in rows],
        "total": total,
        "page": page,
        "limit": limit,
    }


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
    return customer.to_dict()
