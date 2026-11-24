import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.models.document import Document, Scope as DocumentScope
from database.models.document_version import DocumentVersion, DocumentVersionStatus
from database.models.user import User, UserRole
from database.models.workspace import Workspace, WorkspaceMember
from dto.request.create_document import RegisterDocumentRequest, MAX_FILE_SIZE
from dto.request.complete_upload import CompleteUploadRequest
from dto.response.create_document import RegisterDocumentResponse
from dto.response.complete_upload import CompleteUploadResponse
from utils.object_storage import start_upload, finish_upload, abort_upload, delete_object, download_url, resume_part_urls, head_object_etag, move_object, build_object_key
from events import create_event_publisher, DocumentReadyEvent
from utils.exception_handler import ObjectStorageError, ForbiddenError, NotFoundError
from services.shared import (
    log_event,
    forbid,
    not_found,
    conflict,
    get_or_404,
    paginate,
    assert_super_admin_cannot_upload,
    assert_can_manage_organization_docs,
)

logger = logging.getLogger("app.services.document")


def _resolve_upload_context(db: Session, request: RegisterDocumentRequest, current_user):
    """Resolve the workspace and organization the upload belongs to, from server-side
    state rather than trusting the client: workspace-scoped uploads derive the org
    from the workspace, global uploads from the uploader's own organization."""
    if request.workspaceId is None:
        forbid(
            request.scope == DocumentScope.WORKSPACE,
            "workspaceId is required for workspace-scoped documents",
        )
        return None, current_user.organizationId

    workspace = db.get(Workspace, request.workspaceId)
    not_found(workspace is None, "Workspace not found", logger, workspaceId=str(request.workspaceId))
    return workspace, workspace.organizationId


def _authorize_upload(db: Session, current_user, scope: str, organization_id: uuid.UUID, workspace) -> None:
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
        from sqlalchemy import select

        forbid(workspace is None, "workspaceId is required for workspace-scoped documents")
        is_member = db.scalar(
            select(func.count()).select_from(WorkspaceMember).where(
                WorkspaceMember.workspaceId == workspace.id,
                WorkspaceMember.userId == current_user.id,
            )
        )
        forbid(not is_member, "You are not a member of this workspace", logger, userId=str(current_user.id))


def _get_or_create_document(db: Session, request: RegisterDocumentRequest, organization_id: uuid.UUID, current_user) -> Document:
    if request.documentId is None:
        document = Document(
            workspaceId=request.workspaceId,
            scope=request.scope,
            organizationId=organization_id,
            document_name=request.documentName,
            createdBy=current_user.id,
            modifiedBy=current_user.id,
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
    if document.workspaceId != request.workspaceId or document.organizationId != organization_id:
        not_found(
            True,
            "Document does not belong to this workspace",
            logger,
            documentId=str(request.documentId),
            workspaceId=str(request.workspaceId),
        )
    return document


def _create_pending_version(db: Session, document: Document, request: RegisterDocumentRequest, current_user, idempotency_key: str | None = None) -> DocumentVersion:
    document_version = DocumentVersion(
        documentId=document.id,
        mediaType=request.mediaType,
        workspaceId=request.workspaceId,
        fileSize=request.fileSize,
        createdBy=current_user.id,
        modifiedBy=current_user.id,
    )
    if idempotency_key:
        document_version.idempotency_key = idempotency_key
    db.add(document_version)
    db.flush()
    document_version.objectKey = build_object_key(
        str(document.organizationId),
        str(document.id),
        str(document_version.versionId),
        DocumentVersionStatus.PENDING.value,
    )
    document_version.storage_path = document_version.objectKey
    log_event(
        logger,
        "Document version created",
        versionId=document_version.versionId,
        documentId=document.id,
    )
    return document_version


def _replay_register(db: Session, request: RegisterDocumentRequest, current_user, idempotency_key: str) -> RegisterDocumentResponse | None:
    existing = db.scalar(
        select(DocumentVersion).where(DocumentVersion.idempotency_key == idempotency_key)
    )
    if existing is None:
        return None

    forbid(
        existing.createdBy != current_user.id,
        "Idempotency key already used by a different uploader",
        logger,
        idempotencyKey=idempotency_key,
    )
    if existing.status != DocumentVersionStatus.PENDING:
        conflict(
            True,
            "Upload with this idempotency key already completed",
            logger,
            idempotencyKey=idempotency_key,
            versionId=str(existing.versionId),
            status=existing.status.value,
        )
    conflict(
        existing.fileSize != request.fileSize,
        "File size differs from the original attempt for this idempotency key",
        logger,
        idempotencyKey=idempotency_key,
        expectedSize=existing.fileSize,
        actualSize=request.fileSize,
    )
    document = get_or_404(db, Document, existing.documentId, logger, "Parent document not found")
    conflict(
        document.workspaceId != request.workspaceId,
        "Workspace differs from the original attempt for this idempotency key",
        logger,
        idempotencyKey=idempotency_key,
        documentId=str(document.id),
    )

    upload_info = resume_part_urls(existing.objectKey, existing.uploadId, existing.fileSize)
    log_event(
        logger,
        "Register replayed for existing idempotency key",
        documentId=document.id,
        versionId=existing.versionId,
        uploadId=existing.uploadId,
    )
    response = RegisterDocumentResponse(
        documentId=document.id,
        versionId=existing.versionId,
        workspaceId=document.workspaceId,
        scope=document.scope,
        organizationId=document.organizationId,
        documentName=document.document_name,
        upload=upload_info,
    )
    response.message = "Document registered successfully"
    return response


def register_document_handler(db: Session, request: RegisterDocumentRequest, current_user, idempotency_key: str | None = None) -> RegisterDocumentResponse:
    workspace, organization_id = _resolve_upload_context(db, request, current_user)
    _authorize_upload(db, current_user, request.scope, organization_id, workspace)

    # Defense-in-depth: enforce 500MB limit even if DTO validation is bypassed
    forbid(
        request.fileSize > MAX_FILE_SIZE,
        f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024 * 1024)} MB",
        logger,
        fileSize=request.fileSize,
        maxFileSize=MAX_FILE_SIZE,
    )

    if idempotency_key:
        replay = _replay_register(db, request, current_user, idempotency_key)
        if replay is not None:
            return replay

    log_event(
        logger,
        "Registering document",
        documentId=request.documentId,
        organizationId=organization_id,
        workspaceId=request.workspaceId,
        documentName=request.documentName,
        mediaType=request.mediaType.value,
        fileSize=request.fileSize,
        uploadedBy=str(current_user.id),
    )

    try:
        document = _get_or_create_document(db, request, organization_id, current_user)
        document_version = _create_pending_version(db, document, request, current_user, idempotency_key)

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


def _build_complete_response(document, document_version, file_size: int, etag: str, stored_hash: str) -> CompleteUploadResponse:
    response = CompleteUploadResponse(
        documentId=document.id,
        versionId=document_version.versionId,
        status=document_version.status,
        sourceUrl=document_version.source_url,
        fileSize=file_size,
        etag=etag,
        hash=stored_hash,
        workspaceId=document.workspaceId,
        organizationId=document.organizationId,
        documentName=document.document_name,
        mediaType=document_version.mediaType.value,
        createdAt=document_version.createdAt,
    )
    response.message = "Document upload completed successfully"
    return response


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
    document = get_or_404(
        db, Document, document_version.documentId, logger, "Parent document not found",
    )
    workspace_obj = None
    if document.scope == DocumentScope.WORKSPACE and document.workspaceId is not None:
        workspace_obj = db.get(Workspace, document.workspaceId)
    _authorize_upload(db, current_user, document.scope.value, document.organizationId, workspace_obj)

    if document_version.status != DocumentVersionStatus.PENDING:
        conflict(
            request.uploadId != document_version.uploadId,
            "uploadId does not match the one issued for this version",
            logger,
            versionId=version_id,
            expectedUploadId=document_version.uploadId,
        )
        conflict(
            document_version.status == DocumentVersionStatus.ABORTED,
            "Upload for this version was aborted and cannot be completed",
            logger,
            versionId=version_id,
            status=document_version.status.value,
        )
        log_event(
            logger,
            "Complete replayed for already uploaded version",
            documentId=document.id,
            versionId=version_id,
            status=document_version.status.value,
        )
        return _build_complete_response(
            document,
            document_version,
            document_version.fileSize,
            head_object_etag(document_version.objectKey) or document_version.hash,
            document_version.hash,
        )

    conflict(
        request.uploadId != document_version.uploadId,
        "uploadId does not match the one issued for this version",
        logger,
        versionId=version_id,
        expectedUploadId=document_version.uploadId,
    )

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

    if result["fileSize"] != document_version.fileSize:
        abort_upload(document_version.objectKey, request.uploadId)
        delete_object(document_version.objectKey)
        document_version.status = DocumentVersionStatus.ABORTED
        db.commit()
        conflict(
            True,
            f"Uploaded size {result['fileSize']} does not match registered size {document_version.fileSize}",
            logger,
            versionId=version_id,
            expectedSize=document_version.fileSize,
            actualSize=result["fileSize"],
        )

    # Move from pending folder to unprocessed folder (uploaded status)
    old_key = document_version.objectKey
    new_key = build_object_key(
        str(document.organizationId),
        str(document.id),
        str(document_version.versionId),
        DocumentVersionStatus.UPLOADED.value,
    )
    move_object(old_key, new_key)

    document_version.status = DocumentVersionStatus.UPLOADED
    document_version.objectKey = new_key
    document_version.storage_path = new_key
    document_version.source_url = result["finalUrl"]
    stored_hash = request.hash if request.hash else result["etag"]
    document_version.hash = stored_hash
    db.commit()
    db.refresh(document_version)

    log_event(
        logger,
        "Document upload completed",
        documentId=document.id,
        versionId=version_id,
        fileSize=result["fileSize"],
        hashType="sha256" if request.hash else "etag",
        hash=stored_hash,
    )

    try:
        publisher = create_event_publisher()
        publisher.publish_document_ready(
            DocumentReadyEvent(
                document_version_id=str(document_version.versionId),
                user_id=str(current_user.id),
                document_id=str(document.id),
                organization_id=str(document.organizationId),
                workspace_id=str(document.workspaceId) if document.workspaceId else None,
                object_key=document_version.objectKey,
                file_size=document_version.fileSize,
                media_type=document_version.mediaType.value,
                sha256_hash=document_version.hash,
                published_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    except Exception:
        logger.warning(
            "Failed to publish document ready event (non-blocking)",
            extra={"extra_data": {"documentVersionId": str(document_version.versionId)}},
            exc_info=True,
        )

    return _build_complete_response(document, document_version, result["fileSize"], result["etag"], stored_hash)


def transition_to_available(db: Session, document_version: DocumentVersion) -> None:
    """Move document version from unprocessed to safe folder when processing succeeds."""
    if document_version.status == DocumentVersionStatus.AVAILABLE:
        return  # Already in safe

    old_key = document_version.objectKey
    new_key = build_object_key(
        str(document_version.document.organizationId),
        str(document_version.documentId),
        str(document_version.versionId),
        DocumentVersionStatus.AVAILABLE.value,
    )
    move_object(old_key, new_key)

    document_version.status = DocumentVersionStatus.AVAILABLE
    document_version.objectKey = new_key
    document_version.storage_path = new_key
    db.commit()
    log_event(
        logger,
        "Document version moved to safe storage",
        versionId=document_version.versionId,
        documentId=document_version.documentId,
    )


def transition_to_quarantined(db: Session, document_version: DocumentVersion, reason: str) -> None:
    """Move document version to quarantined folder with reason."""
    if document_version.status == DocumentVersionStatus.QUARANTINED:
        return  # Already quarantined

    old_key = document_version.objectKey
    new_key = build_object_key(
        str(document_version.document.organizationId),
        str(document_version.documentId),
        str(document_version.versionId),
        DocumentVersionStatus.QUARANTINED.value,
    )
    move_object(old_key, new_key)

    document_version.status = DocumentVersionStatus.QUARANTINED
    document_version.objectKey = new_key
    document_version.storage_path = new_key
    document_version.quarantine_reason = reason
    db.commit()
    log_event(
        logger,
        "Document version quarantined",
        versionId=document_version.versionId,
        documentId=document_version.documentId,
        reason=reason,
    )


def move_document_version_storage(db: Session, document_version: DocumentVersion, new_status: DocumentVersionStatus, reason: str | None = None) -> None:
    """Move document version between storage folders based on status."""
    if new_status == DocumentVersionStatus.AVAILABLE:
        transition_to_available(db, document_version)
    elif new_status == DocumentVersionStatus.QUARANTINED:
        if not reason:
            raise ValueError("Quarantine reason is required")
        transition_to_quarantined(db, document_version, reason)
    # For other statuses, no move needed (stay in unprocessed)


def delete_document_handler(db: Session, document_id: uuid.UUID, current_user) -> dict:
    if current_user.role == UserRole.SUPER_ADMIN:
        raise ForbiddenError("Super admins cannot manage documents")

    document = get_or_404(db, Document, document_id, logger, "Document not found")
    forbid(
        current_user.organizationId != document.organizationId,
        "You can only manage documents in your own organization",
        logger,
        userId=str(current_user.id),
        documentId=str(document_id),
    )

    if document.scope == DocumentScope.GLOBAL:
        forbid(
            current_user.role != UserRole.ORG_ADMIN,
            "Only organization admins can delete global documents",
            logger,
            userId=str(current_user.id),
            role=current_user.role.value,
        )
    else:
        from database.models.workspace import Workspace as WorkspaceModel
        from services.workspace_service import assert_workspace_admin as _assert_ws_admin

        workspace = get_or_404(
            db, WorkspaceModel, document.workspaceId, logger, "Parent workspace not found",
        )
        member = db.scalar(
            select(func.count()).select_from(WorkspaceMember).where(
                WorkspaceMember.workspaceId == workspace.id,
                WorkspaceMember.userId == current_user.id,
            )
        )
        forbid(not member, "You are not a member of this workspace", logger, userId=str(current_user.id))
        is_uploader = document.createdBy == current_user.id
        if not is_uploader:
            _assert_ws_admin(db, workspace, current_user)

    versions = db.scalars(
        select(DocumentVersion).where(DocumentVersion.documentId == document.id)
    ).all()
    for version in versions:
        if version.status == DocumentVersionStatus.PENDING and version.uploadId and version.objectKey:
            abort_upload(version.objectKey, version.uploadId)
        if version.objectKey:
            try:
                delete_object(version.objectKey)
            except Exception:
                logger.error(
                    "Failed to delete object from storage, continuing with database removal",
                    extra={"extra_data": {"documentId": document.id, "objectKey": version.objectKey}},
                    exc_info=True,
                )

    document_name = document.document_name
    db.delete(document)
    db.commit()
    log_event(
        logger, "Document deleted",
        documentId=document_id,
        documentName=document_name,
        deletedBy=str(current_user.id),
        versionCount=len(versions),
    )
    return {"message": "Document deleted successfully"}


def get_workspace_documents_handler(
    db: Session, workspace_id: uuid.UUID, current_user, page: int, page_size: int
) -> dict:
    from database.models.workspace import Workspace as WorkspaceModel

    workspace = get_or_404(db, WorkspaceModel, workspace_id, logger, "Workspace not found")
    forbid(
        current_user.organizationId != workspace.organizationId,
        "You do not have access to this workspace",
        logger,
        userId=str(current_user.id),
    )
    is_member = db.scalar(
        select(func.count()).select_from(WorkspaceMember).where(
            WorkspaceMember.workspaceId == workspace.id,
            WorkspaceMember.userId == current_user.id,
        )
    )
    forbid(not is_member, "You are not a member of this workspace", logger, userId=str(current_user.id))

    doc_scope = select(Document).where(Document.workspaceId == workspace.id)
    doc_count = select(func.count()).select_from(Document).where(Document.workspaceId == workspace.id)
    result = paginate(db, doc_scope.order_by(Document.createdAt.desc()), doc_count, page, page_size)
    documents = result["items"]

    doc_ids = [doc.id for doc in documents]
    versions_by_doc: dict = {}
    if doc_ids:
        version_rows = db.execute(
            select(DocumentVersion, User.name)
            .outerjoin(User, User.id == DocumentVersion.createdBy)
            .where(DocumentVersion.documentId.in_(doc_ids))
            .order_by(DocumentVersion.createdAt.desc())
        ).all()
        for version, uploader_name in version_rows:
            versions_by_doc.setdefault(version.documentId, []).append((version, uploader_name))

    uploader_names = {
        user_id: name
        for user_id, name in db.execute(
            select(User.id, User.name).where(User.id.in_([doc.createdBy for doc in documents] or [None]))
        ).all()
    } if documents else {}

    rows = []
    for doc in documents:
        versions = versions_by_doc.get(doc.id, [])
        active_version_id = next(
            (v.versionId for v, _ in versions if v.status == DocumentVersionStatus.AVAILABLE.value),
            None,
        )
        version_list = [
            {
                "versionId": v.versionId,
                "status": v.status.value if isinstance(v.status, DocumentVersionStatus) else v.status,
                "isActive": v.versionId == active_version_id,
                "uploadedByName": uploader_name,
                "fileSize": v.fileSize,
                "createdAt": v.createdAt,
            }
            for v, uploader_name in versions
        ]
        rows.append({
            "documentId": doc.id,
            "name": doc.document_name,
            "uploadedByName": uploader_names.get(doc.createdBy),
            "createdAt": doc.createdAt,
            "versionCount": len(versions),
            "versions": version_list,
        })

    return {
        "documents": rows,
        "total": result["total"],
        "page": result["page"],
        "pageSize": page_size,
    }


def get_organization_documents_handler(
    db: Session, organization_id: uuid.UUID, current_user, page: int, page_size: int
) -> dict:
    """List global documents for an organization.
    org_admin: full version trails + upload (all docs)
    org_super_admin/participant: latest available version only (AVAILABLE docs only, read-only)"""
    forbid(
        current_user.organizationId != organization_id,
        "You can only access documents in your own organization",
        logger,
        userId=str(current_user.id),
    )
    is_admin = current_user.role == UserRole.ORG_ADMIN
    is_viewer = current_user.role in (UserRole.PARTICIPANT, UserRole.ORG_SUPER_ADMIN)
    forbid(
        not (is_admin or is_viewer),
        "Not authorized to view global documents",
        logger,
        userId=str(current_user.id),
        role=current_user.role.value,
    )

    # Viewers (participant, org_super_admin) only see latest available version
    show_full_trail = is_admin

    # For viewers, only show documents that have at least one AVAILABLE version
    if is_viewer and not is_admin:
        doc_scope = select(Document).where(
            Document.organizationId == organization_id,
            Document.scope == DocumentScope.GLOBAL,
            Document.id.in_(
                select(DocumentVersion.documentId).where(
                    DocumentVersion.status == DocumentVersionStatus.AVAILABLE
                )
            ),
        )
        doc_count = select(func.count()).select_from(Document).where(
            Document.organizationId == organization_id,
            Document.scope == DocumentScope.GLOBAL,
            Document.id.in_(
                select(DocumentVersion.documentId).where(
                    DocumentVersion.status == DocumentVersionStatus.AVAILABLE
                )
            ),
        )
    else:
        doc_scope = select(Document).where(
            Document.organizationId == organization_id,
            Document.scope == DocumentScope.GLOBAL,
        )
        doc_count = select(func.count()).select_from(Document).where(
            Document.organizationId == organization_id,
            Document.scope == DocumentScope.GLOBAL,
        )
    result = paginate(db, doc_scope.order_by(Document.createdAt.desc()), doc_count, page, page_size)
    documents = result["items"]

    doc_ids = [doc.id for doc in documents]
    versions_by_doc: dict = {}
    if doc_ids:
        version_rows = db.execute(
            select(DocumentVersion, User.name)
            .outerjoin(User, User.id == DocumentVersion.createdBy)
            .where(DocumentVersion.documentId.in_(doc_ids))
            .order_by(DocumentVersion.createdAt.desc())
        ).all()
        for version, uploader_name in version_rows:
            versions_by_doc.setdefault(version.documentId, []).append((version, uploader_name))

    uploader_names = {
        user_id: name
        for user_id, name in db.execute(
            select(User.id, User.name).where(User.id.in_([doc.createdBy for doc in documents] or [None]))
        ).all()
    } if documents else {}

    rows = []
    for doc in documents:
        versions = versions_by_doc.get(doc.id, [])
        active_version_id = next(
            (v.versionId for v, _ in versions if v.status == DocumentVersionStatus.AVAILABLE.value),
            None,
        )
        if show_full_trail:
            version_list = [
                {
                    "versionId": v.versionId,
                    "status": v.status.value if isinstance(v.status, DocumentVersionStatus) else v.status,
                    "isActive": v.versionId == active_version_id,
                    "uploadedByName": uploader_name,
                    "fileSize": v.fileSize,
                    "createdAt": v.createdAt,
                }
                for v, uploader_name in versions
            ]
        else:
            # Only latest available version for viewers (participant, org_super_admin)
            latest_available = next(
                (v for v, _ in versions if v.status == DocumentVersionStatus.AVAILABLE.value),
                None,
            )
            version_list = []
            if latest_available:
                uploader_name = next(
                    (name for v, name in versions if v.versionId == latest_available.versionId),
                    None,
                )
                version_list = [{
                    "versionId": latest_available.versionId,
                    "status": latest_available.status.value if isinstance(latest_available.status, DocumentVersionStatus) else latest_available.status,
                    "isActive": True,
                    "uploadedByName": uploader_name,
                    "fileSize": latest_available.fileSize,
                    "createdAt": latest_available.createdAt,
                }]
        rows.append({
            "documentId": doc.id,
            "name": doc.document_name,
            "uploadedByName": uploader_names.get(doc.createdBy),
            "createdAt": doc.createdAt,
            "versionCount": len(versions),
            "versions": version_list,
        })

    return {
        "documents": rows,
        "total": result["total"],
        "page": result["page"],
        "pageSize": page_size,
    }


def delete_document_version_handler(
    db: Session, document_id: uuid.UUID, version_id: uuid.UUID, current_user
) -> dict:
    if current_user.role == UserRole.SUPER_ADMIN:
        raise ForbiddenError("Super admins cannot manage documents")

    document = get_or_404(db, Document, document_id, logger, "Document not found")
    forbid(
        current_user.organizationId != document.organizationId,
        "You can only manage documents in your own organization",
        logger,
        userId=str(current_user.id),
    )

    if document.scope == DocumentScope.WORKSPACE:
        from database.models.workspace import Workspace as WorkspaceModel
        from services.workspace_service import assert_workspace_access as _assert_ws_access

        workspace = get_or_404(
            db, WorkspaceModel, document.workspaceId, logger, "Parent workspace not found",
        )
        _assert_ws_access(db, workspace, current_user)
    else:
        forbid(
            current_user.role != UserRole.ORG_ADMIN,
            "Only organization admins can delete global document versions",
            logger,
            userId=str(current_user.id),
            role=current_user.role.value,
        )

    version = db.get(DocumentVersion, version_id)
    if version is None or version.documentId != document_id:
        raise NotFoundError("Version not found for this document")

    if version.status == DocumentVersionStatus.PENDING and version.uploadId and version.objectKey:
        abort_upload(version.objectKey, version.uploadId)
    if version.objectKey:
        try:
            delete_object(version.objectKey)
        except Exception:
            logger.error(
                "Failed to delete version object from storage, continuing with database removal",
                extra={"extra_data": {"versionId": version_id, "objectKey": version.objectKey}},
                exc_info=True,
            )

    db.delete(version)
    db.flush()

    remaining = db.scalar(
        select(func.count()).select_from(DocumentVersion).where(DocumentVersion.documentId == document_id)
    ) or 0
    if remaining == 0:
        document_name = document.document_name
        db.delete(document)
        db.commit()
        log_event(
            logger, "Document deleted after last version removed",
            documentId=document_id,
            documentName=document_name,
            deletedBy=str(current_user.id),
        )
        return {"message": "Version deleted. It was the last version, so the document was removed too."}

    db.commit()
    log_event(
        logger, "Document version deleted",
        documentId=document_id,
        versionId=version_id,
        deletedBy=str(current_user.id),
    )
    return {"message": "Version deleted successfully"}


def get_document_version_download_handler(
    db: Session, document_id: uuid.UUID, version_id: uuid.UUID, current_user
) -> dict:
    document = get_or_404(db, Document, document_id, logger, "Document not found")
    forbid(
        current_user.organizationId != document.organizationId,
        "You do not have access to this document",
        logger,
        userId=str(current_user.id),
    )

    if document.scope == DocumentScope.WORKSPACE:
        from database.models.workspace import Workspace as WorkspaceModel
        from services.workspace_service import assert_workspace_access as _assert_ws_access

        workspace = get_or_404(
            db, WorkspaceModel, document.workspaceId, logger, "Parent workspace not found",
        )
        _assert_ws_access(db, workspace, current_user)

    version = db.get(DocumentVersion, version_id)
    if version is None or version.documentId != document_id:
        raise NotFoundError("Version not found for this document")

    # Allow org_participant and org_super_admin to download global documents
    if document.scope == DocumentScope.GLOBAL:
        forbid(
            current_user.role not in (UserRole.ORG_ADMIN, UserRole.ORG_SUPER_ADMIN, UserRole.PARTICIPANT),
            "Not authorized to download this document",
            logger,
            userId=str(current_user.id),
            role=current_user.role.value,
        )

    conflict(
        version.status not in (DocumentVersionStatus.AVAILABLE, DocumentVersionStatus.UPLOADED),
        f"This version is {version.status.value} and cannot be downloaded",
        logger,
        versionId=version_id,
        status=version.status.value,
    )

    filename = document.document_name
    if document.scope == DocumentScope.WORKSPACE:
        extension = version.mediaType.value
        if not filename.lower().endswith(f".{extension}"):
            filename = f"{filename}.{extension}"

    # Use storage_path for the actual file location
    object_key = version.storage_path or version.objectKey
    url = download_url(object_key, filename)
    log_event(
        logger, "Download URL issued",
        documentId=document_id,
        versionId=version_id,
        userId=str(current_user.id),
    )
    return {"url": url, "filename": filename}


def get_processable_document_versions(
    db: Session, limit: int = 10
) -> list[dict]:
    """Return oldest document versions ready for processing.

    Filters for versions with status UPLOADED or AVAILABLE that haven't been
    picked up for processing yet. Ordered by created_at ascending (oldest first).
    """
    from database.models.document_version import DocumentVersion, DocumentVersionStatus
    from database.models.document import Document, Scope as DocumentScope

    versions = db.execute(
        select(DocumentVersion, Document)
        .join(Document, Document.id == DocumentVersion.documentId)
        .where(
            DocumentVersion.status.in_([DocumentVersionStatus.UPLOADED, DocumentVersionStatus.AVAILABLE]),
            Document.scope == DocumentScope.GLOBAL,
        )
        .order_by(DocumentVersion.createdAt.asc())
        .limit(limit)
    ).all()

    result = []
    for version, document in versions:
        result.append({
            "versionId": str(version.versionId),
            "documentId": str(document.id),
            "documentName": document.document_name,
            "organizationId": str(document.organizationId),
            "objectKey": version.objectKey,
            "fileSize": version.fileSize,
            "mediaType": version.mediaType.value,
            "sha256Hash": version.hash,
            "status": version.status.value,
            "createdAt": version.createdAt.isoformat() if version.createdAt else None,
        })

    return result
