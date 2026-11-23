import uuid
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.document import Document
from database.models.document_version import DocumentVersion, DocumentVersionStatus
from dto.request.create_document import RegisterDocumentRequest
from dto.request.complete_upload import CompleteUploadRequest
from dto.request.update_document import UpdateDocumentRequest
from dto.response.create_document import RegisterDocumentResponse
from dto.response.complete_upload import CompleteUploadResponse
from dto.response.get_documents import GetAllDocumentsResponse, DocumentResponse
from dto.response.delete_response import DeleteResponse
from utils.object_storage import start_upload, finish_upload, abort_upload
from utils.exception_handler import NotFoundError, ConflictError, ObjectStorageError

logger = logging.getLogger("app.services.document")


def register_document_handler(db: Session, request: RegisterDocumentRequest) -> RegisterDocumentResponse:
    logger.info(
        "Registering document",
        extra={"extra_data": {
            "documentId": request.documentId,
            "organizationId": request.organizationId,
            "workspaceId": request.workspaceId,
            "documentName": request.documentName,
            "mediaType": request.mediaType.value,
            "fileSize": request.fileSize,
        }},
    )

    try:
        if request.documentId is None:
            document = Document(
                workspaceId=request.workspaceId,
                scope=request.scope,
                organizationId=request.organizationId,
                document_name=request.documentName,
            )
            db.add(document)
            db.flush()
            logger.info(
                "New document created",
                extra={"extra_data": {"documentId": document.id}},
            )
        else:
            document = db.get(Document, request.documentId)
            if document is None:
                logger.warning(
                    "Parent document not found",
                    extra={"extra_data": {"documentId": request.documentId}},
                )
                raise NotFoundError(f"No document exists with document_id {request.documentId}")

        object_key = f"{document.organizationId}/{document.id}/{uuid.uuid4()}/{request.documentName}"

        document_version = DocumentVersion(
            documentId=document.id,
            mediaType=request.mediaType,
            workspaceId=request.workspaceId,
            objectKey=object_key,
            fileSize=request.fileSize,
            createdBy=request.createdBy,
            modifiedBy=request.createdBy,
        )
        db.add(document_version)
        db.flush()
        logger.info(
            "Document version created",
            extra={"extra_data": {"versionId": document_version.versionId, "documentId": document.id}},
        )

        try:
            upload_info = start_upload(object_key, request.fileSize)
        except Exception as exc:
            logger.error(
                "Presigned URL generation failed",
                extra={"extra_data": {"versionId": document_version.versionId, "objectKey": object_key}},
                exc_info=True,
            )
            raise ObjectStorageError("Failed to initialize file upload") from exc

        document_version.uploadId = upload_info["uploadId"]

        db.commit()
        db.refresh(document)
        db.refresh(document_version)
        logger.info(
            "Document registered successfully",
            extra={"extra_data": {
                "documentId": document.id,
                "versionId": document_version.versionId,
                "uploadId": upload_info["uploadId"],
                "totalParts": len(upload_info["partUrls"]),
            }},
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

    except (NotFoundError, ObjectStorageError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.error(
            "Unexpected error while registering document",
            extra={"extra_data": {"documentId": request.documentId, "documentName": request.documentName}},
            exc_info=True,
        )
        raise


def complete_upload_handler(db: Session, version_id: uuid.UUID, request: CompleteUploadRequest) -> CompleteUploadResponse:
    logger.info(
        "Completing document upload",
        extra={"extra_data": {"versionId": version_id, "uploadId": request.uploadId, "partCount": len(request.parts)}},
    )

    document_version = db.get(DocumentVersion, version_id)
    if document_version is None:
        logger.warning("Document version not found", extra={"extra_data": {"versionId": version_id}})
        raise NotFoundError(f"No document version exists with version_id {version_id}")

    if document_version.status != DocumentVersionStatus.PENDING:
        logger.warning(
            "Upload completion attempted for non-pending version",
            extra={"extra_data": {"versionId": version_id, "status": document_version.status.value}},
        )
        raise ConflictError(f"Upload for this version is already {document_version.status.value}")

    if request.uploadId != document_version.uploadId:
        logger.warning(
            "Upload id mismatch",
            extra={"extra_data": {"versionId": version_id, "expectedUploadId": document_version.uploadId}},
        )
        raise ConflictError("uploadId does not match the one issued for this version")

    document = db.get(Document, document_version.documentId)
    if document is None:
        logger.error(
            "Parent document missing for version",
            extra={"extra_data": {"versionId": version_id, "documentId": document_version.documentId}},
        )
        raise NotFoundError("Parent document not found")

    uploaded_parts = [{"PartNumber": part.partNumber, "ETag": part.etag} for part in request.parts]

    try:
        result = finish_upload(document_version.objectKey, request.uploadId, uploaded_parts)
    except Exception as exc:
        logger.error(
            "Failed to complete multipart upload in object storage",
            extra={"extra_data": {"versionId": version_id, "objectKey": document_version.objectKey}},
            exc_info=True,
        )
        raise ObjectStorageError("Failed to complete file upload") from exc

    if result["fileSize"] != document_version.fileSize:
        abort_upload(document_version.objectKey, request.uploadId)
        logger.error(
            "Uploaded object size mismatch",
            extra={"extra_data": {
                "versionId": version_id,
                "expectedSize": document_version.fileSize,
                "actualSize": result["fileSize"],
            }},
        )
        raise ConflictError(
            f"Uploaded size {result['fileSize']} does not match registered size {document_version.fileSize}"
        )

    document_version.status = DocumentVersionStatus.AVAILABLE
    document_version.source_url = result["finalUrl"]
    document_version.hash = result["etag"]
    db.commit()
    db.refresh(document_version)

    logger.info(
        "Document upload completed",
        extra={"extra_data": {
            "documentId": document.id,
            "versionId": version_id,
            "fileSize": result["fileSize"],
            "etag": result["etag"],
        }},
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


def get_document_handler(db: Session, document_id: uuid.UUID) -> DocumentResponse:
    document = db.get(Document, document_id)
    if document is None:
        logger.warning("Document not found", extra={"extra_data": {"documentId": document_id}})
        raise NotFoundError("Document not found")
    response = DocumentResponse.model_validate(document)
    response.message = "Document fetched successfully"
    return response


def get_all_documents_handler(db: Session) -> GetAllDocumentsResponse:
    documents = db.scalars(select(Document)).all()
    response = GetAllDocumentsResponse(documents=documents)
    response.message = "Documents fetched successfully"
    return response


def update_document_handler(db: Session, document_id: uuid.UUID, request: UpdateDocumentRequest) -> DocumentResponse:
    document = db.get(Document, document_id)
    if document is None:
        logger.warning("Document not found", extra={"extra_data": {"documentId": document_id}})
        raise NotFoundError("Document not found")
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(document, field, value)
    db.commit()
    db.refresh(document)
    logger.info("Document updated", extra={"extra_data": {"documentId": document.id}})
    response = DocumentResponse.model_validate(document)
    response.message = "Document updated successfully"
    return response


def delete_document_handler(db: Session, document_id: uuid.UUID) -> DeleteResponse:
    document = db.get(Document, document_id)
    if document is None:
        logger.warning("Document not found", extra={"extra_data": {"documentId": document_id}})
        raise NotFoundError("Document not found")
    db.delete(document)
    db.commit()
    logger.info("Document deleted", extra={"extra_data": {"documentId": document_id}})
    return DeleteResponse(message="Document deleted successfully")
