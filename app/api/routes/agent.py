from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["agent"])


@router.get("/agent", response_class=HTMLResponse)
def agent_page() -> HTMLResponse:
    html = Path("app/templates/agent.html").read_text(encoding="utf-8")
    return HTMLResponse(html)
