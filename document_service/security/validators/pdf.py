import fitz

from .base import FileSecurityCheck
from ..models import SecurityReport, SecurityCheckResult
from ..config import DEFAULT_CONFIG, SecurityConfig


class PDFSecurityCheck(FileSecurityCheck):

    def __init__(
        self,
        config: SecurityConfig = DEFAULT_CONFIG,
    ):
        super().__init__(config)

    def _check_catalog_actions(self, doc):

        catalog_xref = doc.pdf_catalog()

        for key in ("OpenAction", "AA"):

            value_type, value = doc.xref_get_key(
                catalog_xref,
                key,
            )

            if value_type not in ("null", "none"):
                return False

        return True

    def _check_page_actions(self, doc):

        for page in doc:

            value_type, value = doc.xref_get_key(
                page.xref,
                "AA",
            )

            if value_type not in ("null", "none"):
                return False

            for link in page.get_links():

                if link.get("kind") == fitz.LINK_LAUNCH:
                    return False

                uri = link.get("uri", "")

                if uri.lower().startswith(
                    ("javascript:", "data:", "file:")
                ):
                    return False

        return True

    def _check_dangerous_actions(self, doc):

        dangerous_actions = (
            "/JavaScript",
            "/Launch",
            "/SubmitForm",
            "/ImportData",
        )

        for xref in range(1, doc.xref_length()):

            obj = doc.xref_object(xref)

            if any(action in obj for action in dangerous_actions):
                return False

        return True

    def check(
        self,
        file_path: str,
        mime_type: str,
        file_size: int,
    ) -> SecurityReport:

        base = super().check(
            file_path,
            mime_type,
            file_size,
        )

        if not base.passed:
            return base

        checks = base.checks.copy()
        reasons = []

        try:

            with fitz.open(file_path) as doc:

                # 1. Encryption
                checks["encryption"] = not doc.needs_pass

                if not checks["encryption"]:
                    reasons.append("Password-protected PDF")

                # 2. Repair status
                checks["parseable"] = not doc.is_repaired

                if not checks["parseable"]:
                    reasons.append("PDF required structural repair")

                # 3. Page count
                page_count = len(doc)

                checks["page_count"] = (
                    0 < page_count <= self.config.max_pdf_pages
                )

                # 4. Embedded files
                embedded_count = doc.embfile_count()

                checks["embedded_files"] = (
                    embedded_count <= self.config.max_embedded_files
                )

                # 5. Catalog actions
                checks["catalog_actions"] = (
                    self._check_catalog_actions(doc)
                )

                # 6. Page actions
                checks["page_actions"] = (
                    self._check_page_actions(doc)
                )

                # 7. Additional dangerous action objects
                checks["dangerous_actions"] = (
                    self._check_dangerous_actions(doc)
                )

                # 8. Form fields
                form_count = 0

                for page in doc:

                    widgets = page.widgets()

                    if widgets:
                        for _ in widgets:
                            form_count += 1

                            if form_count > self.config.max_form_fields:
                                break

                    if form_count > self.config.max_form_fields:
                        break

                checks["form_fields"] = (
                    form_count <= self.config.max_form_fields
                )

            failed = [
                key for key, value in checks.items()
                if not value
            ]

            if failed:

                return SecurityReport(
                    result=SecurityCheckResult.QUARANTINE,
                    checks=checks,
                    reason="PDF security validation failed",
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

            checks["pdf_parseable"] = False

            return SecurityReport(
                result=SecurityCheckResult.QUARANTINE,
                checks=checks,
                reason=f"PDF inspection failed: {exc}",
                file_path=file_path,
                mime_type=mime_type,
                file_size=file_size,
                sha256=base.sha256,
            )