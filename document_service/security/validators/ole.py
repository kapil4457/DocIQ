import olefile

from oletools.olevba import VBA_Parser

from .base import FileSecurityCheck
from document_service.security.models import SecurityReport, SecurityCheckResult
from document_service.security.config import DEFAULT_CONFIG, SecurityConfig


class OLESecurityCheck(FileSecurityCheck):

    def __init__(
        self,
        config: SecurityConfig = DEFAULT_CONFIG,
    ):
        super().__init__(config)

    def _inspect_structure(self, file_path: str):

        with olefile.OleFileIO(file_path) as ole:

            streams = [
                "/".join(parts).lower()
                for parts in ole.listdir()
            ]

            if not streams:
                raise ValueError("OLE document contains no streams")

            # Inspect VBA-related streams.
            has_vba = any(
                "vba" in stream
                or "macros" in stream
                for stream in streams
            )

            # Inspect embedded object indicators.
            has_embeddings = any(
                "objectpool" in stream
                or "oleobject" in stream
                for stream in streams
            )

            return {
                "ole_integrity": True,
                "macros": not (
                    has_vba and self.config.reject_macros
                ),
                "embedded_objects": not (
                    has_embeddings
                    and self.config.reject_embedded_objects
                ),
            }

    def _inspect_vba(self, file_path: str):

        parser = VBA_Parser(file_path)

        try:

            if not parser.detect_vba_macros():
                return {
                    "vba_detected": False,
                    "vba_analysis": True,
                }

            # Detecting VBA is not equivalent to proving
            # that the macro is malicious.
            if self.config.reject_macros:
                return {
                    "vba_detected": True,
                    "vba_analysis": False,
                }

            return {
                "vba_detected": True,
                "vba_analysis": True,
            }

        finally:
            parser.close()

    def check(
        self,
        file_path: str,
        mime_type: str,
        file_size: int,
    ):

        base = super().check(
            file_path,
            mime_type,
            file_size,
        )

        if not base.passed:
            return base

        checks = base.checks.copy()

        try:

            structure_checks = self._inspect_structure(
                file_path
            )

            checks.update(structure_checks)

            vba_checks = self._inspect_vba(
                file_path
            )

            checks.update(vba_checks)

            failed = [
                key for key, value in checks.items()
                if not value
            ]

            if failed:

                return SecurityReport(
                    result=SecurityCheckResult.QUARANTINE,
                    checks=checks,
                    reason="Legacy Office security checks failed",
                    details=str(failed),
                    file_path=file_path,
                    mime_type=mime_type,
                    file_size=file_size,
                    sha256=base.sha256,
                )

            return SecurityReport(
                result=SecurityCheckResult.PASS,
                checks=checks,
                file_path=file_path,
                mime_type=mime_type,
                file_size=file_size,
                sha256=base.sha256,
            )

        except Exception as exc:

            checks["ole_inspection"] = False

            return SecurityReport(
                result=SecurityCheckResult.QUARANTINE,
                checks=checks,
                reason=f"OLE inspection failed: {exc}",
                file_path=file_path,
                mime_type=mime_type,
                file_size=file_size,
                sha256=base.sha256,
            )