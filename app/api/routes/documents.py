from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.documents import DocumentUploadResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> DocumentUploadResponse:
    content = await file.read()
    return DocumentService().save_and_ingest(
        filename=file.filename or "upload.txt",
        content=content,
        content_type=file.content_type,
        session=session,
    )

