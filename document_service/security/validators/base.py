from pathlib import Path

from document_service.security.config import DEFAULT_CONFIG, SecurityConfig
from document_service.security.models import SecurityReport, SecurityCheckResult
from document_service.security.utils.streaming import inspect_file_stream


MIME_EXTENSIONS = {

    "application/pdf": {".pdf"},

    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        {".docx"},

    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        {".xlsx"},

    "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        {".pptx"},

    "text/csv": {".csv"},
    "text/plain": {".txt"},
    "text/markdown": {".md", ".markdown"},
    "text/html": {".html", ".htm"},
    "image/png": {".png"},
}


MAGIC_BYTES = {

    "application/pdf": b"%PDF-",

    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        b"PK\x03\x04",

    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        b"PK\x03\x04",

    "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        b"PK\x03\x04",
}


class FileSecurityCheck:

    def __init__(
        self,
        config: SecurityConfig = DEFAULT_CONFIG,
    ):
        self.config = config

    def check(
        self,
        file_path: str,
        mime_type: str,
        file_size: int,
    ) -> SecurityReport:

        checks = {}
        reasons = []

        try:

            path = Path(file_path)

            if not path.is_file():
                raise OSError("Not a regular file")

            # Stage 1: Streaming inspection
            stream = inspect_file_stream(
                file_path,
                self.config.max_file_size,
                self.config.chunk_size,
            )

            checks["file_exists"] = True

            checks["file_size"] = (
                stream.file_size == file_size
            )

            if not checks["file_size"]:
                reasons.append("File size mismatch")

            checks["supported_mime"] = (
                mime_type in MIME_EXTENSIONS
            )

            if not checks["supported_mime"]:
                reasons.append("Unsupported MIME type")

            allowed_extensions = MIME_EXTENSIONS.get(
                mime_type,
                set(),
            )

            checks["extension"] = (
                path.suffix.lower() in allowed_extensions
            )

            if not checks["extension"]:
                reasons.append("Extension does not match MIME type")

            expected_magic = MAGIC_BYTES.get(mime_type)

            if expected_magic:
                checks["magic_bytes"] = stream.header.startswith(
                    expected_magic
                )
            else:
                # Text files do not have a reliable universal signature.
                checks["magic_bytes"] = True

            if not checks["magic_bytes"]:
                reasons.append("Magic-byte validation failed")

            checks["sha256"] = bool(stream.sha256)

            failed = [
                key for key, value in checks.items()
                if not value
            ]

            if failed:

                critical = {
                    "file_exists",
                    "file_size",
                    "magic_bytes",
                }

                result = (
                    SecurityCheckResult.QUARANTINE
                    if critical.intersection(failed)
                    else SecurityCheckResult.FAIL
                )

                return SecurityReport(
                    result=result,
                    checks=checks,
                    reason="; ".join(reasons),
                    file_path=file_path,
                    mime_type=mime_type,
                    file_size=stream.file_size,
                    sha256=stream.sha256,
                )

            return SecurityReport(
                result=SecurityCheckResult.PASS,
                checks=checks,
                file_path=file_path,
                mime_type=mime_type,
                file_size=stream.file_size,
                sha256=stream.sha256,
            )

        except Exception as exc:

            return SecurityReport(
                result=SecurityCheckResult.QUARANTINE,
                checks={**checks, "stream_inspection": False},
                reason=str(exc),
                file_path=file_path,
                mime_type=mime_type,
                file_size=file_size,
            )