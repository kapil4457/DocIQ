import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.db_engine import get_db
from dto.request.create_document import RegisterDocumentRequest
from dto.request.complete_upload import CompleteUploadRequest
from dto.response.create_document import RegisterDocumentResponse
from dto.response.complete_upload import CompleteUploadResponse
from services.document_service import (
    register_document_handler,
    complete_upload_handler,
)
from utils.auth_dependencies import CurrentUser
from utils.exception_handler import NotFoundError, ConflictError, ObjectStorageError

logger = logging.getLogger("app.controllers.document")

router = APIRouter(prefix="/document", tags=["Document"])


@router.post("/register/init", response_model=RegisterDocumentResponse)
def register_document(
    request: RegisterDocumentRequest,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
):
    return register_document_handler(db, request, user)


@router.post("/register/{version_id}/complete", response_model=CompleteUploadResponse)
def complete_document_upload(
    version_id: uuid.UUID,
    request: CompleteUploadRequest,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
):
    try:
        return complete_upload_handler(db, version_id, request, user)
    except (NotFoundError, ConflictError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail)
