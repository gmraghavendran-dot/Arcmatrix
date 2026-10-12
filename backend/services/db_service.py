from collections.abc import Iterable
from sqlalchemy import text
from sqlalchemy.orm import Session


def fetch_all(db: Session, sql: str, params: dict | None = None) -> list[dict]:
    rows = db.execute(text(sql), params or {}).mappings().all()
    return [dict(row) for row in rows]


def fetch_one(db: Session, sql: str, params: dict | None = None) -> dict | None:
    row = db.execute(text(sql), params or {}).mappings().first()
    return dict(row) if row else None
