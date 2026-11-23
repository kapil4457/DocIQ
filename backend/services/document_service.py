import uuid
import logging

from sqlalchemy.orm import Session

from database.models.document import Document
from database.models.document_version import DocumentVersion, DocumentVersionStatus
from database.models.user import UserRole
from dto.request.create_document import RegisterDocumentRequest
from dto.request.complete_upload import CompleteUploadRequest
from dto.response.create_document import RegisterDocumentResponse
from dto.response.complete_upload import CompleteUploadResponse
from utils.object_storage import start_upload, finish_upload, abort_upload
from utils.exception_handler import ObjectStorageError
from services.shared import (
    log_event,
    forbid,
    not_found,
    conflict,
    get_or_404,
    assert_super_admin_cannot_upload,
    assert_can_manage_organization_docs,
)

logger = logging.getLogger("app.services.document")


def _authorize_upload(db: Session, current_user, scope: str, organization_id: uuid.UUID, workspace_id) -> None:
    assert_super_admin_cannot_upload(current_user)
    forbid(
        scope == "global" and current_user.role != UserRole.ORG_ADMIN,
        "Only organization admins can upload global documents",
        logger,
        userId=str(current_user.id),
        role=current_user.role.value,
    )
    assert_can_manage_organization_docs(current_user, organization_id)
    if scope == "workspace":
        from database.models.workspace import Workspace, WorkspaceMember
        from sqlalchemy import select, func

        forbid(workspace_id is None, "workspaceId is required for workspace-scoped documents")
        workspace = db.get(Workspace, workspace_id)
        not_found(workspace is None, "Workspace not found", logger, workspaceId=str(workspace_id))
        forbid(
            workspace.organizationId != organization_id or workspace.organizationId != current_user.organizationId,
            "Workspace does not belong to your organization",
            logger,
            userId=str(current_user.id),
            workspaceId=str(workspace_id),
        )
        is_member = db.scalar(
            select(func.count()).select_from(WorkspaceMember).where(
                WorkspaceMember.workspaceId == workspace.id,
                WorkspaceMember.userId == current_user.id,
            )
        )
        forbid(not is_member, "You are not a member of this workspace", logger, userId=str(current_user.id))


def _get_or_create_document(db: Session, request: RegisterDocumentRequest) -> Document:
    if request.documentId is None:
        document = Document(
            workspaceId=request.workspaceId,
            scope=request.scope,
            organizationId=request.organizationId,
            document_name=request.documentName,
        )
        db.add(document)
        db.flush()
        log_event(logger, "New document created", documentId=document.id)
        return document

    document = get_or_404(
        db,
        Document,
        request.documentId,
        logger,
        f"No document exists with document_id {request.documentId}",
    )
    return document


def _create_pending_version(db: Session, document: Document, request: RegisterDocumentRequest, current_user) -> DocumentVersion:
    document_version = DocumentVersion(
        documentId=document.id,
        mediaType=request.mediaType,
        workspaceId=request.workspaceId,
        fileSize=request.fileSize,
        createdBy=current_user.id,
        modifiedBy=current_user.id,
    )
    db.add(document_version)
    db.flush()
    document_version.objectKey = f"{document.organizationId}/{document.id}/{document_version.versionId}"
    log_event(
        logger,
        "Document version created",
        versionId=document_version.versionId,
        documentId=document.id,
    )
    return document_version


def register_document_handler(db: Session, request: RegisterDocumentRequest, current_user) -> RegisterDocumentResponse:
    _authorize_upload(db, current_user, request.scope, request.organizationId, request.workspaceId)
    log_event(
        logger,
        "Registering document",
        documentId=request.documentId,
        organizationId=request.organizationId,
        workspaceId=request.workspaceId,
        documentName=request.documentName,
        mediaType=request.mediaType.value,
        fileSize=request.fileSize,
        uploadedBy=str(current_user.id),
    )

    try:
        document = _get_or_create_document(db, request)
        document_version = _create_pending_version(db, document, request, current_user)

        try:
            upload_info = start_upload(document_version.objectKey, request.fileSize)
        except Exception as exc:
            log_event(
                logger,
                "Presigned URL generation failed",
                level=logging.ERROR,
                versionId=document_version.versionId,
                objectKey=document_version.objectKey,
            )
            raise ObjectStorageError("Failed to initialize file upload") from exc

        document_version.uploadId = upload_info["uploadId"]
        db.commit()
        db.refresh(document)
        db.refresh(document_version)
        log_event(
            logger,
            "Document registered successfully",
            documentId=document.id,
            versionId=document_version.versionId,
            uploadId=upload_info["uploadId"],
            totalParts=len(upload_info["partUrls"]),
        )

        response = RegisterDocumentResponse(
            documentId=document.id,
            versionId=document_version.versionId,
            workspaceId=document.workspaceId,
            scope=document.scope,
            organizationId=document.organizationId,
            documentName=request.documentName,
            upload=upload_info,
        )
        response.message = "Document registered successfully"
        return response

    except ObjectStorageError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        log_event(
            logger,
            "Unexpected error while registering document",
            level=logging.ERROR,
            documentId=request.documentId,
            documentName=request.documentName,
        )
        raise


def complete_upload_handler(db: Session, version_id: uuid.UUID, request: CompleteUploadRequest, current_user) -> CompleteUploadResponse:
    log_event(
        logger,
        "Completing document upload",
        versionId=version_id,
        uploadId=request.uploadId,
        partCount=len(request.parts),
    )

    document_version = get_or_404(
        db, DocumentVersion, version_id, logger,
        f"No document version exists with version_id {version_id}",
    )
    conflict(
        document_version.status != DocumentVersionStatus.PENDING,
        f"Upload for this version is already {document_version.status.value}",
        logger,
        versionId=version_id,
        status=document_version.status.value,
    )
    conflict(
        request.uploadId != document_version.uploadId,
        "uploadId does not match the one issued for this version",
        logger,
        versionId=version_id,
        expectedUploadId=document_version.uploadId,
    )

    document = get_or_404(
        db, Document, document_version.documentId, logger, "Parent document not found",
    )
    _authorize_upload(db, current_user, document.scope.value, document.organizationId, document.workspaceId)

    uploaded_parts = [{"PartNumber": part.partNumber, "ETag": part.etag} for part in request.parts]

    try:
        result = finish_upload(document_version.objectKey, request.uploadId, uploaded_parts)
    except Exception as exc:
        log_event(
            logger,
            "Failed to complete multipart upload in object storage",
            level=logging.ERROR,
            versionId=version_id,
            objectKey=document_version.objectKey,
        )
        raise ObjectStorageError("Failed to complete file upload") from exc

    conflict(
        result["fileSize"] != document_version.fileSize,
        f"Uploaded size {result['fileSize']} does not match registered size {document_version.fileSize}",
        logger,
        versionId=version_id,
        expectedSize=document_version.fileSize,
        actualSize=result["fileSize"],
    )
    if result["fileSize"] != document_version.fileSize:
        abort_upload(document_version.objectKey, request.uploadId)

    document_version.status = DocumentVersionStatus.AVAILABLE
    document_version.source_url = result["finalUrl"]
    document_version.hash = result["etag"]
    db.commit()
    db.refresh(document_version)

    log_event(
        logger,
        "Document upload completed",
        documentId=document.id,
        versionId=version_id,
        fileSize=result["fileSize"],
        etag=result["etag"],
    )

    response = CompleteUploadResponse(
        documentId=document.id,
        versionId=document_version.versionId,
        status=document_version.status,
        sourceUrl=document_version.source_url,
        fileSize=result["fileSize"],
        etag=result["etag"],
        workspaceId=document.workspaceId,
        organizationId=document.organizationId,
        documentName=document.document_name,
        mediaType=document_version.mediaType.value,
        createdAt=document_version.createdAt,
    )
    response.message = "Document upload completed successfully"
    return response
