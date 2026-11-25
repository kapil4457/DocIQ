from .base import FileSecurityCheck
from document_service.security.models import SecurityReport, SecurityCheckResult
from document_service.security.config import DEFAULT_CONFIG, SecurityConfig


class TextSecurityCheck(FileSecurityCheck):

    def __init__(
        self,
        config: SecurityConfig = DEFAULT_CONFIG,
    ):
        super().__init__(config)

    def check(
        self,
        file_path,
        mime_type,
        file_size,
    ):

        base = super().check(
            file_path,
            mime_type,
            file_size,
        )

        if not base.passed:
            return base

        checks = base.checks.copy()
        reasons = []

        line_count = 0
        max_line_length = 0

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="strict",
            ) as f:

                for line in f:

                    line_count += 1

                    current_length = len(line)

                    max_line_length = max(
                        max_line_length,
                        current_length,
                    )

                    if line_count > self.config.max_text_lines:
                        raise ValueError("Maximum line count exceeded")

                    if current_length > self.config.max_line_length:
                        raise ValueError("Maximum line length exceeded")

            checks["encoding"] = True

            checks["line_count"] = (
                line_count <= self.config.max_text_lines
            )

            checks["line_length"] = (
                max_line_length <= self.config.max_line_length
            )

        except UnicodeDecodeError:
            checks["encoding"] = False
            reasons.append("Invalid UTF-8 encoding")

        except ValueError as exc:
            checks["content_limits"] = False
            reasons.append(str(exc))

        except Exception as exc:
            checks["parseable"] = False
            reasons.append(str(exc))

        failed = [
            key for key, value in checks.items()
            if not value
        ]

        if failed:

            return SecurityReport(
                result=SecurityCheckResult.FAIL,
                checks=checks,
                reason="; ".join(reasons),
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