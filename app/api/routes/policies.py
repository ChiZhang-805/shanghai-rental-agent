from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.policy import PolicyIngestResponse
from app.services.policy_service import PolicyService

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.post("/ingest", response_model=PolicyIngestResponse)
def ingest_policies(session: Session = Depends(get_db)) -> PolicyIngestResponse:
    return PolicyService().ingest_directory(session, Path("data/policies"))

