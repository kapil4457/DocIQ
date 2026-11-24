import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.db_engine import get_db
from dto.request.create_document import RegisterDocumentRequest
from dto.request.complete_upload import CompleteUploadRequest
from dto.response.create_document import RegisterDocumentResponse
from dto.response.complete_upload import CompleteUploadResponse
from dto.response.get_workspace_documents import GetWorkspaceDocumentsResponse
from dto.response.base_response import BaseResponse
from services.document_service import (
    register_document_handler,
    complete_upload_handler,
    delete_document_handler,
    get_workspace_documents_handler,
    get_organization_documents_handler,
    delete_document_version_handler,
    get_document_version_download_handler,
)
from utils.auth_dependencies import CurrentUser
from utils.exception_handler import NotFoundError, ForbiddenError, ConflictError, ObjectStorageError

logger = logging.getLogger("app.controllers.document")

router = APIRouter(prefix="/document", tags=["Document"])


@router.get("/list", response_model=GetWorkspaceDocumentsResponse)
def get_workspace_documents(
    workspaceId: uuid.UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
):
    try:
        result = get_workspace_documents_handler(db, workspaceId, user, page, pageSize)
        return GetWorkspaceDocumentsResponse(**result, message="Documents fetched successfully")
    except (NotFoundError, ForbiddenError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/global", response_model=GetWorkspaceDocumentsResponse)
def get_organization_documents(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
):
    try:
        result = get_organization_documents_handler(db, user.organizationId, user, page, pageSize)
        return GetWorkspaceDocumentsResponse(**result, message="Global documents fetched successfully")
    except (NotFoundError, ForbiddenError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.delete("/{document_id}/versions/{version_id}", response_model=BaseResponse)
def delete_document_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return BaseResponse(**delete_document_version_handler(db, document_id, version_id, user))
    except (NotFoundError, ForbiddenError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail)


@router.get("/{document_id}/versions/{version_id}/download")
def download_document_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return get_document_version_download_handler(db, document_id, version_id, user)
    except (NotFoundError, ForbiddenError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except ConflictError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/register/init", response_model=RegisterDocumentResponse)
def register_document(
    request: RegisterDocumentRequest,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=64)] = None,
):
    return register_document_handler(db, request, user, idempotency_key)


@router.delete("/{document_id}", response_model=BaseResponse)
def delete_document(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
):
    try:
        return BaseResponse(**delete_document_handler(db, document_id, user))
    except (NotFoundError, ForbiddenError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail)


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
