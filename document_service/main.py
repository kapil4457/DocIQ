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

from config import get_settings
from database import init_db, get_db_sync
from models import DocumentVersion, DocumentVersionStatus
from document_service.security.validators import SecurityCheckerFactory, SecurityCheckResult, run_security_check

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
    """Fetch document versions with PENDING status, oldest first."""
    with get_db_session() as db:
        versions = db.query(DocumentVersion).filter(
            DocumentVersion.status == DocumentVersionStatus.PENDING
        ).order_by(DocumentVersion.createdAt.asc()).limit(limit).all()

        # Detach from session
        for v in versions:
            db.expunge(v)
        return versions


def update_version_status(version_id: uuid.UUID, status: DocumentVersionStatus,
                          quarantine_reason: str | None = None) -> bool:
    """Update document version status."""
    try:
        with get_db_session() as db:
            version = db.query(DocumentVersion).filter(
                DocumentVersion.versionId == version_id
            ).first()
            if not version:
                logger.warning(f"Version {version_id} not found")
                return False

            version.status = status
            version.modifiedAt = datetime.now(timezone.utc)
            if quarantine_reason:
                version.quarantine_reason = quarantine_reason
            db.commit()
            return True
    except Exception as e:
        logger.exception(f"Failed to update version {version_id} status: {e}")
        return False


def update_version_status_with_retry(version_id: uuid.UUID, status: DocumentVersionStatus,
                                     retry_count: int, quarantine_reason: str | None = None) -> bool:
    """Update document version status with retry count."""
    try:
        with get_db_session() as db:
            version = db.query(DocumentVersion).filter(
                DocumentVersion.versionId == version_id
            ).first()
            if not version:
                logger.warning(f"Version {version_id} not found")
                return False

            version.status = status
            version.modifiedAt = datetime.now(timezone.utc)
            version.retry_count = retry_count
            if quarantine_reason:
                version.quarantine_reason = quarantine_reason
            db.commit()
            return True
    except Exception as e:
        logger.exception(f"Failed to update version {version_id} status with retry: {e}")
        return False


def download_file_from_r2(object_key: str, local_path: str) -> bool:
    """Download file from R2 to local path for security checking."""
    try:
        from utils.object_storage import download_url
        import requests

        url = download_url(object_key, "temp")
        response = requests.get(url, stream=True, timeout=60)
        if response.status_code != 200:
            logger.error(f"Failed to download {object_key}: {response.status_code}")
            return False

        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.exception(f"Failed to download file {object_key}: {e}")
        return False


def run_security_checks_on_version(version) -> dict:
    """Run security checks on a document version.

    Returns:
        dict with keys: 'result' (PASS/FAIL/QUARANTINE), 'reason', 'details', 'temp_path' (if PASS)
    """
    if not version.storage_path:
        return {
            "result": "FAIL",
            "reason": "No storage path available for security check",
            "details": "Document version has no storage path"
        }

    # Download file locally for security checking
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_path = tmp.name

    try:
        # Download file
        if not download_file_from_r2(version.storage_path, temp_path):
            return {
                "result": "FAIL",
                "reason": "Failed to download file for security check",
                "details": f"Could not download {version.storage_path}"
            }

        # Get file size
        file_size = os.path.getsize(temp_path)

        # Determine MIME type from mediaType
        from models import MediaType
        mime_type = version.mediaType.value if version.mediaType else "application/octet-stream"

        # Run security check
        from document_service.security.validators import run_security_check
        report = run_security_check(temp_path, mime_type, file_size)

        if report.result == SecurityCheckResult.PASS:
            # Keep temp file for next processing stages
            return {
                "result": "PASS",
                "reason": "Security check passed",
                "details": "File is safe for processing",
                "checks": report.checks,
                "temp_path": temp_path,
            }
        else:
            # Clean up temp file on FAIL/QUARANTINE
            if os.path.exists(temp_path):
                os.unlink(temp_path)

            # QUARANTINE gets specific reason, FAIL gets generic
            if report.result == SecurityCheckResult.QUARANTINE:
                reason = report.reason or "Security check failed"
                details = report.details
            else:  # FAIL
                reason = "Security check failed"
                details = report.details or report.reason

            return {
                "result": report.result.value,
                "reason": reason,
                "details": details,
                "checks": report.checks,
            }
    except Exception as e:
        # Clean up temp file on exception
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        logger.exception(f"Security check failed with exception: {e}")
        return {
            "result": "FAIL",
            "reason": f"Security check error: {str(e)}",
            "details": str(e),
        }


def process_version(version) -> bool:
    """Process a single document version through security checks."""
    logger.info(f"Processing version {version.versionId} (document: {version.documentId})")

    # Update status to PROCESSING
    if not update_version_status(version.versionId, DocumentVersionStatus.PROCESSING):
        return False

    # Run security checks
    result = run_security_checks_on_version(version)

    if result["result"] == "PASS":
        # Security passed - mark as UPLOADED (ready for next processing stage)
        # KEEP the temp file for next processing stages
        success = update_version_status(version.versionId, DocumentVersionStatus.UPLOADED)
        if success:
            logger.info(f"Version {version.versionId} passed security checks")
        return success

    elif result["result"] == "QUARANTINE":
        # Security failed critically - quarantine
        reason = result.get("reason", "Security check failed")
        success = update_version_status(
            version.versionId,
            DocumentVersionStatus.QUARANTINED,
            quarantine_reason=reason
        )
        if success:
            logger.warning(f"Version {version.versionId} quarantined: {reason}")
        return success

    else:  # FAIL
        # Non-critical failure - check retry count
        max_retries = 5
        if version.retry_count >= max_retries:
            # Max retries exceeded - quarantine
            actual_reason = result.get("details") or result.get("reason") or "Security check failed"
            reason = f"Max retries exceeded. Failure reason: {actual_reason}"
            success = update_version_status(
                version.versionId,
                DocumentVersionStatus.QUARANTINED,
                quarantine_reason=reason
            )
            if success:
                logger.warning(f"Version {version.versionId} quarantined after max retries: {reason}")
            return success
        else:
            # Increment retry count and back to UPLOADED for retry
            failed_checks = [k for k, v in result.get("checks", {}).items() if not v]
            reason_detail = result.get("details") or result.get("reason")
            if failed_checks:
                logger.warning(f"Version {version.versionId} failed security (attempt {version.retry_count + 1}/{5}): {result.get('details') or result.get('reason')}. Failed checks: {', '.join(failed_checks)}")
            else:
                logger.warning(f"Version {version.versionId} failed security (attempt {version.retry_count + 1}/{5}): {result.get('details') or result.get('reason')}")

            # Increment retry count and mark as UPLOADED for retry
            success = update_version_status_with_retry(version.versionId, DocumentVersionStatus.UPLOADED, version.retry_count + 1)
            return success


def run_worker_loop():
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
                    process_version(version)
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

    # Run worker loop
    run_worker_loop()

    logger.info("Document Service Background Task Stopped")


if __name__ == "__main__":
    main()