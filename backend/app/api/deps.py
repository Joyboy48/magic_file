from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends

from app.db.session import SessionLocal


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

