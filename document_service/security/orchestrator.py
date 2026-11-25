
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Optional

from document_service.security.config import SecurityConfig
from document_service.security.models import (
    SecurityCheckResult,
    SecurityReport,
)
from document_service.security.validators.pdf import PDFSecurityCheck
from document_service.security.validators.office import OfficeSecurityCheck
from document_service.security.validators.ole import OLESecurityCheck
from document_service.security.validators.csv import CsvSecurityCheck
from document_service.security.validators.text import TextSecurityCheck
from document_service.security.validators.html import HtmlSecurityCheck
from document_service.security.validators.png import PngSecurityCheck
from document_service.security.scanners.antivirus import (
    ClamAVScanner,
    AntivirusStatus,
)

logger = logging.getLogger(__name__)


# Explicit mapping is preferable to inferring a validator
# from a filename or a MIME substring.
VALIDATOR_MAP = {
    # PDF
    "application/pdf": PDFSecurityCheck,

    # OOXML Office formats
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        OfficeSecurityCheck,

    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        OfficeSecurityCheck,

    "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        OfficeSecurityCheck,

    # Legacy Microsoft Office formats (OLE compound files)
    "application/msword": OLESecurityCheck,
    "application/vnd.ms-excel": OLESecurityCheck,
    "application/vnd.ms-powerpoint": OLESecurityCheck,

    # CSV
    "text/csv": CsvSecurityCheck,

    # Plain text / Markdown
    "text/plain": TextSecurityCheck,
    "text/markdown": TextSecurityCheck,

    # HTML (static content; active content rejected by policy)
    "text/html": HtmlSecurityCheck,

    # Images
    "image/png": PngSecurityCheck,
}


class DocumentSecurityOrchestrator:
    """
    Coordinates document validation and antivirus scanning.

    A file is approved only when:
      1. Its format-specific validator passes.
      2. Antivirus scanning reports CLEAN.
      3. Antivirus scanning is available when required.

    This class does not sanitize documents or make them safe
    for unrestricted parsing. Approved files should still be
    processed in resource-limited workers.
    """

    def __init__(
        self,
        config: Optional[SecurityConfig] = None,
        antivirus_scanner: Optional[ClamAVScanner] = None,
    ):
        self.config = config or SecurityConfig()
        self.antivirus_scanner = antivirus_scanner

        self.validators = {
            mime_type: validator_class(self.config)
            for mime_type, validator_class in VALIDATOR_MAP.items()
        }

    def inspect(
        self,
        file_path: str,
        mime_type: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> SecurityReport:
        """
        Inspect an uploaded document.

        Args:
            file_path: Path to the staged uploaded file.
            mime_type: MIME type determined by your upload layer.
            filename: Original uploaded filename.

        Returns:
            SecurityReport containing all validation outcomes.
        """

        path = Path(file_path)
        filename = filename or path.name

        checks: dict[str, bool] = {}
        details: dict = {}

        # -------------------------------------------------
        # 1. Basic file existence checks
        # -------------------------------------------------
        if not path.exists() or not path.is_file():
            return self._report(
                SecurityCheckResult.FAIL,
                "File does not exist or is not a regular file.",
                checks,
                details,
                file_path,
            )

        try:
            actual_size = path.stat().st_size
        except OSError as exc:
            return self._report(
                SecurityCheckResult.FAIL,
                f"Unable to access file: {exc}",
                checks,
                details,
                file_path,
            )

        if actual_size == 0:
            return self._report(
                SecurityCheckResult.FAIL,
                "Empty files are not accepted.",
                checks,
                details,
                file_path,
            )

        checks["file_exists"] = True
        checks["file_non_empty"] = True

        # -------------------------------------------------
        # 2. Resolve MIME type
        # -------------------------------------------------
        # Prefer a MIME type established by your upload layer
        # using libmagic. mimetypes.guess_type() only uses the
        # filename and must not be treated as content detection.
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(filename)

        if not mime_type:
            return self._report(
                SecurityCheckResult.FAIL,
                "Unable to determine file MIME type.",
                checks,
                details,
                file_path,
            )

        mime_type = mime_type.lower().split(";")[0].strip()
        details["mime_type"] = mime_type
        details["filename"] = filename
        details["size_bytes"] = actual_size

        # -------------------------------------------------
        # 3. Find format-specific validator
        # -------------------------------------------------
        validator = self.validators.get(mime_type)

        if validator is None:
            return self._report(
                SecurityCheckResult.FAIL,
                f"Unsupported file type: {mime_type}",
                checks,
                details,
                file_path,
            )

        checks["supported_format"] = True

        # -------------------------------------------------
        # 4. Format-specific validation
        # -------------------------------------------------
        try:
            validation_result = validator.check(
                file_path=str(path),
                mime_type=mime_type,
                file_size=path.stat().st_size,
            )
        except Exception:
            logger.exception(
                "Format validation failed unexpectedly for %s",
                filename,
            )

            return self._report(
                SecurityCheckResult.QUARANTINE,
                "Unexpected error during format validation.",
                checks,
                details,
                file_path,
            )

        checks["format_validation"] = (
            validation_result.result == SecurityCheckResult.PASS
        )

        details["format_validation"] = getattr(
            validation_result, "details", {}
        )

        if validation_result.result != SecurityCheckResult.PASS:
            return self._report(
                validation_result.result,
                getattr(
                    validation_result,
                    "reason",
                    "Format validation failed.",
                ),
                checks,
                details,
                file_path,
            )

        # -------------------------------------------------
        # 5. Antivirus scanning
        # -------------------------------------------------
        if self.config.antivirus_enabled:
            if self.antivirus_scanner is None:
                if self.config.antivirus_required:
                    checks["antivirus"] = False

                    return self._report(
                        SecurityCheckResult.QUARANTINE,
                        "Antivirus scanner is required but not configured.",
                        checks,
                        details,
                        file_path,
                    )

                checks["antivirus"] = False
                details["antivirus"] = "Skipped: scanner not configured."

            else:
                try:
                    logger.info(f"Starting antivirus scan for file: {path} (exists: {path.exists()})")
                    av_result = self.antivirus_scanner.scan(str(path))
                    logger.info(f"Antivirus result: {av_result}")

                except Exception:
                    logger.exception(
                        "Antivirus scan failed for %s",
                        filename,
                    )

                    checks["antivirus"] = False

                    return self._report(
                        SecurityCheckResult.QUARANTINE,
                        "Antivirus scan failed or scanner is unavailable.",
                        checks,
                        details,
                        file_path,
                    )

                details["antivirus"] = {
                    "status": av_result.status.value,
                    "message": av_result.reason,
                    "signature_version": getattr(
                        av_result, "signature_version", None
                    ),
                }

                if av_result.status == AntivirusStatus.INFECTED:
                    checks["antivirus"] = False

                    return self._report(
                        SecurityCheckResult.QUARANTINE,
                        "Malware detected by antivirus scanner.",
                        checks,
                        details,
                        file_path,
                    )

                if av_result.status == AntivirusStatus.ERROR:
                    checks["antivirus"] = False

                    return self._report(
                        SecurityCheckResult.QUARANTINE,
                        "Antivirus scan could not be completed.",
                        checks,
                        details,
                        file_path,
                    )

                if av_result.status != AntivirusStatus.CLEAN:
                    checks["antivirus"] = False

                    return self._report(
                        SecurityCheckResult.QUARANTINE,
                        "Antivirus returned an unknown status.",
                        checks,
                        details,
                        file_path,
                    )

                checks["antivirus"] = True

        else:
            if self.config.antivirus_required:
                return self._report(
                    SecurityCheckResult.QUARANTINE,
                    "Antivirus is required but disabled in configuration.",
                    checks,
                    details,
                    file_path,
                )

            checks["antivirus"] = False
            details["antivirus"] = "Disabled by configuration."

        # -------------------------------------------------
        # 6. Final decision
        # -------------------------------------------------
        return self._report(
            SecurityCheckResult.PASS,
            "File passed all configured security checks.",
            checks,
            details,
            file_path,
        )

    @staticmethod
    def _report(
        status: SecurityCheckResult,
        reason: str,
        checks: dict,
        details: dict,
        file_path: str,
    ) -> SecurityReport:
        """
        Build the final security report.

        Adapt field names here if your SecurityReport dataclass
        uses a slightly different schema.
        """
        return SecurityReport(
            result=status,
            reason=reason,
            checks=checks,
            details=details,
            file_path=file_path,
        )
