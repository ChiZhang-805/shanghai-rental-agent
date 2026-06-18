from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.schemas.social_insight import SocialInsightRequest, SocialInsightResponse
from app.agents.social_insight_agent import SocialInsightAgent
from app.services.image_service import ImageService

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.post("/social", response_model=SocialInsightResponse)
async def social_insight(
    request: Request,
    file: UploadFile | None = File(default=None),
    session: Session = Depends(get_db),
) -> SocialInsightResponse:
    content_type = request.headers.get("content-type", "")
    payload: SocialInsightRequest
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        text = str(form.get("text") or "") or None
        user_context = str(form.get("user_context") or "") or None
        image_path = None
        if file is not None:
            settings = get_settings()
            upload_dir = settings.upload_dir
            upload_dir.mkdir(parents=True, exist_ok=True)
            original_name = Path(file.filename or "social_upload.png").name
            if not ImageService.is_allowed_image_upload(original_name, file.content_type):
                raise HTTPException(status_code=415, detail="只支持 png、jpg、jpeg、webp 图片。")
            suffix = Path(original_name).suffix.lower()
            if not suffix:
                suffix = ImageService.suffix_for_content_type(file.content_type) or ".png"
            image_path = str(upload_dir / f"social_{uuid4().hex}{suffix}")
            content = await file.read()
            if len(content) > settings.max_upload_mb * 1024 * 1024:
                raise HTTPException(status_code=413, detail="上传文件超过大小限制。")
            Path(image_path).write_bytes(content)
        payload = SocialInsightRequest(
            source_type="uploaded_image" if image_path else "pasted_text",
            text=text,
            image_path=image_path,
            user_context=user_context,
        )
    else:
        data = await request.json()
        payload = SocialInsightRequest.model_validate(data)
    return SocialInsightAgent().extract(payload, session=session)
