import logging
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.customer import Customer

logger = logging.getLogger(__name__)

FLASK_BASE_URL = "http://mock-server:5000"
BATCH_SIZE = 50


def _parse_customer(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce raw dict fields to proper Python types for SQLAlchemy."""
    dob = raw.get("date_of_birth")
    if isinstance(dob, str) and dob:
        try:
            dob = date.fromisoformat(dob)
        except ValueError:
            dob = None

    created = raw.get("created_at")
    if isinstance(created, str) and created:
        try:
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            created = None

    balance = raw.get("account_balance")
    if balance is not None:
        balance = Decimal(str(balance))

    return {
        "customer_id": raw["customer_id"],
        "first_name": raw["first_name"],
        "last_name": raw["last_name"],
        "email": raw["email"],
        "phone": raw.get("phone"),
        "address": raw.get("address"),
        "date_of_birth": dob,
        "account_balance": balance,
        "created_at": created,
    }


def fetch_all_customers() -> List[Dict[str, Any]]:
    """Fetch every customer from the Flask mock server, handling pagination."""
    all_customers: List[Dict[str, Any]] = []
    page = 1
    limit = BATCH_SIZE

    with httpx.Client(timeout=30) as client:
        while True:
            resp = client.get(
                f"{FLASK_BASE_URL}/api/customers",
                params={"page": page, "limit": limit},
            )
            resp.raise_for_status()
            payload = resp.json()

            batch = payload.get("data", [])
            all_customers.extend(batch)
            logger.info("Fetched page %d — %d records so far", page, len(all_customers))

            total = payload.get("total", 0)
            if len(all_customers) >= total or not batch:
                break
            page += 1

    return all_customers


def upsert_customers(db: Session, customers: List[Dict[str, Any]]) -> int:
    """Insert or update customers in PostgreSQL. Returns count of processed rows."""
    if not customers:
        return 0

    parsed = [_parse_customer(c) for c in customers]

    stmt = pg_insert(Customer).values(parsed)
    stmt = stmt.on_conflict_do_update(
        index_elements=["customer_id"],
        set_={
            "first_name": stmt.excluded.first_name,
            "last_name": stmt.excluded.last_name,
            "email": stmt.excluded.email,
            "phone": stmt.excluded.phone,
            "address": stmt.excluded.address,
            "date_of_birth": stmt.excluded.date_of_birth,
            "account_balance": stmt.excluded.account_balance,
            "created_at": stmt.excluded.created_at,
        },
    )
    db.execute(stmt)
    db.commit()
    return len(parsed)
