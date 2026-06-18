from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.supervisor import SupervisorAgent
from app.api.deps import get_db
from app.api.key_overrides import request_settings_overrides
from app.config import temporary_settings_override
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: Session = Depends(get_db),
    key_overrides: dict[str, str] = Depends(request_settings_overrides),
) -> ChatResponse:
    with temporary_settings_override(key_overrides):
        return await SupervisorAgent().handle_async(request.message, session=session)
