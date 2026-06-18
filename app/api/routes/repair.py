from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.repair_agent import RepairAgent
from app.api.deps import get_db
from app.schemas.repair import RepairTriageRequest, RepairTriageResponse

router = APIRouter(prefix="/api/repair", tags=["repair"])


@router.post("/triage", response_model=RepairTriageResponse)
def triage_repair(
    request: RepairTriageRequest, session: Session = Depends(get_db)
) -> RepairTriageResponse:
    return RepairAgent().triage(
        request.description,
        image_path=request.image_path,
        session=session,
    )

