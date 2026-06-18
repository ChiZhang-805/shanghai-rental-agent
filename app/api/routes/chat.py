from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.supervisor import SupervisorAgent
from app.api.deps import get_db
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, session: Session = Depends(get_db)) -> ChatResponse:
    return await SupervisorAgent().handle_async(request.message, session=session)
