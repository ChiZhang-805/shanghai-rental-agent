from typing import Any

from sqlalchemy import JSON

try:
    from pgvector.sqlalchemy import Vector as PgVector
except Exception:  # pragma: no cover - only used when pgvector is not installed
    PgVector = None


def vector_column_type(dimensions: int) -> Any:
    if PgVector is None:
        return JSON
    return PgVector(dimensions)

