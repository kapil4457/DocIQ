"""Document Service - Background Task Entry Point.

This service runs as a background worker that:
1. Polls for document versions with status PENDING
2. Runs file security checks on each document
7. Updates status based on security check results
8. Processes documents one by one until queue is empty
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

from document_service.config import get_settings
from document_service.database import init_db, get_db_sync
from document_service.models import DocumentVersion, DocumentVersionStatus, MediaType
from document_service.security import DocumentSecurityOrchestrator, SecurityConfig, SecurityCheckResult
from document_service.security.scanners.antivirus import ClamAVScanner

# Canonical mapping from the DB MediaType enum to real MIME types AND the
# file extension used when staging downloads for validation/AV scanning.
# Single source of truth so mime and staged extension can never disagree.
MEDIA_TYPE_MAP = {
    MediaType.PDF: ("application/pdf", ".pdf"),
    MediaType.DOCX: ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    MediaType.TXT: ("text/plain", ".txt"),
    MediaType.MD: ("text/markdown", ".md"),
    MediaType.PNG: ("image/png", ".png"),
    MediaType.HTML: ("text/html", ".html"),
    MediaType.CSV: ("text/csv", ".csv"),
    MediaType.XLSX: ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    MediaType.PPTX: ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("document-service")

settings = get_settings()


@contextmanager
def get_db_session():
    """Context manager for database session."""
    db = get_db_sync()
    try:
        yield db
    finally:
        db.close()


def fetch_pending_versions(limit: int = 10) -> list:
    """Fetch document versions queued for security checks, oldest first.

    UPLOADED is the canonical queue state (fresh uploads AND retries -
    retries are distinguished by retry_count > 0).
    SECURITY_PENDING is only ever found on crash recovery: it means a worker
    marked a version as claimed but died before finishing. Re-picking it is
    safe (checks are idempotent).
    """
    with get_db_session() as db:
        versions = db.query(DocumentVersion).filter(
            DocumentVersion.status.in_([DocumentVersionStatus.UPLOADED, DocumentVersionStatus.SECURITY_PENDING])
        ).order_by(DocumentVersion.createdAt.asc()).limit(limit).all()

        # Detach from session
        for v in versions:
            db.expunge(v)
        return versions


def update_version_status(version_id: uuid.UUID, status: DocumentVersionStatus,
                          quarantine_reason: str | None = None,
                          retry_count: int | None = None) -> bool:
    """Update document version status and shift the R2 object folder to match.

    Invariant: objectKey/storage_path always point to the key where the file
    actually exists. If the R2 move fails, the old key is kept (file still
    there) and the failure is logged loudly.
    """
    try:
        with get_db_session() as db:
            version = db.query(DocumentVersion).filter(
                DocumentVersion.versionId == version_id
            ).first()
            if not version:
                logger.warning(f"Version {version_id} not found")
                return False

            old_status = version.status
            old_key = version.objectKey
            new_key = old_key

            if old_status != status and old_key:
                from document_service.models import Document
                from document_service.utils.object_storage import build_object_key, move_object

                document = db.query(Document).filter(
                    Document.id == version.documentId
                ).first()
                if document:
                    candidate_key = build_object_key(
                        str(document.organizationId),
                        str(document.id),
                        str(version.versionId),
                        status.value,
                    )
                    if candidate_key != old_key:
                        try:
                            move_object(old_key, candidate_key)
                            new_key = candidate_key
                        except Exception:
                            # Move failed: keep old key (file still exists there),
                            # commit the status change, and surface the error.
                            logger.exception(
                                f"R2 folder shift FAILED for version {version_id}: "
                                f"{old_key} -> {candidate_key}. Keys kept at old location."
                            )
                else:
                    logger.warning(
                        f"Document {version.documentId} not found; cannot compute new "
                        f"object key for version {version_id}. Status updated without move."
                    )

            version.status = status
            version.objectKey = new_key
            version.storage_path = new_key
            version.modifiedAt = datetime.now(timezone.utc)
            if quarantine_reason:
                version.quarantine_reason = quarantine_reason
            if retry_count is not None:
                version.retry_count = retry_count
            db.commit()
            return True
    except Exception as e:
        logger.exception(f"Failed to update version {version_id} status: {e}")
        return False


def update_version_status_with_retry(version_id: uuid.UUID, status: DocumentVersionStatus,
                                     retry_count: int, quarantine_reason: str | None = None) -> bool:
    """Update document version status with retry count."""
    return update_version_status(version_id, status, quarantine_reason, retry_count)


def download_file_from_r2(object_key: str, local_path: str) -> bool:
    """Download file from R2 to local path for security checking."""
    try:
        from document_service.utils.object_storage import get_object
        return get_object(object_key, local_path)
    except Exception as e:
        logger.exception(f"Failed to download file {object_key}: {e}")
        return False


def run_security_checks_on_version(version, security_orchestrator: DocumentSecurityOrchestrator) -> dict:
    """Run security checks on a document version.

    Returns:
        dict with keys: 'status' (PASS/FAIL/QUARANTINE), 'reason', 'details', 'temp_path' (if PASS)
    """
    if not version.storage_path:
        return {
            "status": "FAIL",
            "reason": "No storage path available for security check",
            "details": "Document version has no storage path"
        }

    # Extension must reflect THIS VERSION's mediaType, not the document name.
    # A PDF uploaded as a new version of a PNG document must be staged as
    # .pdf - the document name still says .png (it's just a display label),
    # and staging it as .png would fail extension-vs-MIME validation.
    import tempfile
    import os

    shared_temp_dir = settings.security_scan_dir
    os.makedirs(shared_temp_dir, exist_ok=True)

    suffix = MEDIA_TYPE_MAP.get(version.mediaType, ("", ""))[1]

    with tempfile.NamedTemporaryFile(delete=False, dir=shared_temp_dir, suffix=suffix) as tmp:
        temp_path = tmp.name

    try:
        # Download file
        if not download_file_from_r2(version.storage_path, temp_path):
            return {
                "status": "RETRY",  # transient: network/storage hiccup, worth re-trying
                "reason": "Failed to download file for security check",
                "details": f"Could not download {version.storage_path}"
            }

        # MIME type for the security orchestrator - from the shared map,
        # derived from THIS version's mediaType.
        media_entry = MEDIA_TYPE_MAP.get(version.mediaType)
        if not media_entry:
            return {
                "status": "FAIL",
                "reason": "Unsupported media type",
                "details": f"MediaType {version.mediaType.value if version.mediaType else None} has no MIME mapping"
            }
        mime_type = media_entry[0]

        # Get document name for the orchestrator
        document_name = "unknown"
        try:
            with get_db_session() as db:
                from document_service.models import Document
                doc = db.query(Document).filter(Document.id == version.documentId).first()
                if doc:
                    document_name = doc.document_name
        except Exception:
            pass

        # Run security check using orchestrator
        report = security_orchestrator.inspect(temp_path, mime_type=mime_type, filename=document_name)

        # Temp file has served its purpose (validation + ClamAV scan);
        # the source of truth remains in R2, so always clean it up.
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        if report.result == SecurityCheckResult.PASS:
            return {
                "status": "PASS",
                "reason": "Security check passed",
                "details": "File is safe for processing",
                "checks": report.checks,
            }
        else:
            # Always surface the specific reason (quarantine AND fail);
            # failed check names are appended so the UI can show detail.
            reason = report.reason or "Security check failed"
            failed_checks = [k for k, v in (report.checks or {}).items() if not v]
            if failed_checks:
                reason += f" (failed: {', '.join(failed_checks)})"

            # details can be a dict (orchestrator details) - stringify for DB
            details = report.details
            if isinstance(details, dict):
                parts = []
                for k, v in details.items():
                    if k == "format_validation" and isinstance(v, dict):
                        continue  # redundant with reason
                    parts.append(f"{k}: {v}")
                details = "; ".join(parts) if parts else None

            return {
                "status": report.result.value,
                "reason": reason,
                "details": details,
                "checks": report.checks,
            }
    except Exception as e:
        # Clean up temp file on exception
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        logger.exception(f"Security check failed with exception: {e}")
        return {
            "status": "FAIL",
            "reason": f"Security check error: {str(e)}",
            "details": str(e),
        }


def process_version(version, security_orchestrator: DocumentSecurityOrchestrator) -> bool:
    """Process a single document version through security checks."""
    logger.info(f"Processing version {version.versionId} (document: {version.documentId})")

    # Claim: SECURITY_RUNNING means "a worker is actively checking this".
    # (UPLOADED is the queue state; SECURITY_PENDING only ever appears as a
    # crash-recovery leftover, and claiming it works the same way.)
    if not update_version_status(version.versionId, DocumentVersionStatus.SECURITY_RUNNING):
        return False
    logger.info(f"Version {version.versionId} claimed for security checks (SECURITY_RUNNING)")

    # Run security checks
    result = run_security_checks_on_version(version, security_orchestrator)
    # Normalize: result["status"] is a SecurityCheckResult enum value ("pass"/"fail"/"quarantine")
    result_status = str(result["status"]).lower()

    if result_status == "pass":
        # Security passed - mark as AVAILABLE (ready for ingestion)
        success = update_version_status(version.versionId, DocumentVersionStatus.AVAILABLE)
        if success:
            logger.info(f"Version {version.versionId} passed security checks, marked AVAILABLE")
        return success

    elif result_status == "quarantine":
        # Security failed critically - mark as SECURITY_FAILED
        reason = result.get("reason", "Security check failed")
        success = update_version_status(
            version.versionId,
            DocumentVersionStatus.SECURITY_FAILED,
            quarantine_reason=reason
        )
        if success:
            logger.warning(f"Version {version.versionId} security failed: {reason}")
        return success

    elif result_status == "retry":
        # Transient failure (e.g. download hiccup): requeue for another pass.
        # These are the only failures worth retrying; deterministic format/
        # policy violations quarantine immediately instead.
        max_retries = 5
        if version.retry_count >= max_retries:
            reason = result.get("reason") or "Repeated transient failures during security check"
            success = update_version_status(
                version.versionId,
                DocumentVersionStatus.SECURITY_FAILED,
                quarantine_reason=reason
            )
            if success:
                logger.warning(f"Version {version.versionId} failed transiently after max retries: {reason}")
            return success
        logger.warning(f"Version {version.versionId} transient failure (attempt {version.retry_count + 1}/{max_retries}): {result.get('reason')}")
        return update_version_status_with_retry(version.versionId, DocumentVersionStatus.UPLOADED, version.retry_count + 1)

    else:  # FAIL (deterministic policy/format violation)
        # These failures are deterministic: the same bytes will fail the same
        # check every time. Retrying cannot help, so quarantine immediately
        # with the specific reason.
        reason = result.get("reason") or result.get("details") or "Security check failed"
        success = update_version_status(
            version.versionId,
            DocumentVersionStatus.SECURITY_FAILED,
            quarantine_reason=reason
        )
        if success:
            logger.warning(f"Version {version.versionId} security failed: {reason}")
        return success


def run_worker_loop(security_orchestrator: DocumentSecurityOrchestrator):
    """Main worker loop - fetch and process pending versions."""
    logger.info("Starting document service worker...")
    logger.info(f"Poll interval: {settings.worker_poll_interval}s, Batch size: {settings.worker_batch_size}")

    while True:
        try:
            # Fetch pending versions
            versions = fetch_pending_versions(limit=settings.worker_batch_size)

            if not versions:
                logger.debug("No pending versions, sleeping...")
                time.sleep(settings.worker_poll_interval)
                continue

            logger.info(f"Found {len(versions)} pending versions to process")

            # Process each version
            for version in versions:
                try:
                    process_version(version, security_orchestrator)
                except Exception as e:
                    logger.exception(f"Error processing version {version.versionId}: {e}")
                    # Mark as UPLOADED for retry
                    update_version_status(version.versionId, DocumentVersionStatus.UPLOADED)

        except KeyboardInterrupt:
            logger.info("Worker interrupted, shutting down...")
            break
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            time.sleep(settings.worker_poll_interval)


def main():
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Document Service Background Task Starting")
    logger.info("=" * 50)

    # Initialize database
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")

    # Initialize security orchestrator
    logger.info("Initializing security orchestrator...")
    logger.info(f"ClamAV: {settings.clamav_host}:{settings.clamav_port}, scan dir: {settings.security_scan_dir}")
    security_config = SecurityConfig()
    clamav_scanner = ClamAVScanner(
        host=settings.clamav_host,
        port=settings.clamav_port,
        timeout=settings.clamav_timeout,
        shared_mount_host=settings.security_scan_dir,
        shared_mount_container=settings.clamav_shared_mount_container,
    )
    security_orchestrator = DocumentSecurityOrchestrator(config=security_config, antivirus_scanner=clamav_scanner)
    logger.info("Security orchestrator initialized")

    # Run worker loop
    run_worker_loop(security_orchestrator)

    logger.info("Document Service Background Task Stopped")


if __name__ == "__main__":
    main()