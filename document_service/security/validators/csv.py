import csv

from .base import FileSecurityCheck
from document_service.security.models import SecurityReport, SecurityCheckResult
from document_service.security.config import DEFAULT_CONFIG, SecurityConfig


class CsvSecurityCheck(FileSecurityCheck):

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

        row_count = 0
        expected_columns = None
        max_field_length = 0

        try:

            csv.field_size_limit(
                self.config.max_csv_field_size
            )

            with open(
                file_path,
                "r",
                encoding="utf-8-sig",
                errors="strict",
                newline="",
            ) as f:

                reader = csv.reader(
                    f,
                    strict=True,
                )

                for row in reader:

                    row_count += 1

                    if row_count > self.config.max_csv_rows:
                        raise ValueError("CSV row limit exceeded")

                    if not row:
                        continue

                    column_count = len(row)

                    if column_count > self.config.max_csv_columns:
                        raise ValueError("CSV column limit exceeded")

                    if expected_columns is None:
                        expected_columns = column_count

                    elif column_count != expected_columns:
                        raise ValueError(
                            f"Inconsistent column count at row {row_count}"
                        )

                    for field in row:
                        max_field_length = max(
                            max_field_length,
                            len(field),
                        )

            checks["encoding"] = True
            checks["csv_parseable"] = True
            checks["row_count"] = row_count > 0
            checks["column_consistency"] = True
            checks["field_length"] = (
                max_field_length <= self.config.max_csv_field_size
            )

            if row_count == 0:
                reasons.append("CSV contains no records")

        except UnicodeDecodeError:
            checks["encoding"] = False
            reasons.append("Invalid UTF-8 encoding")

        except (csv.Error, ValueError) as exc:
            checks["csv_parseable"] = False
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