import zipfile

from defusedxml import ElementTree as ET

from .base import FileSecurityCheck
from .zip import ZipSecurityValidator, ZipSecurityError

from document_service.security.models import SecurityReport, SecurityCheckResult
from document_service.security.config import DEFAULT_CONFIG, SecurityConfig


class OfficeSecurityCheck(FileSecurityCheck):

    FORMATS = {

        "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            {
                "main": "word/document.xml",
                "required": {
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "word/document.xml",
                },
                "kind": "docx",
            },

        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            {
                "main": "xl/workbook.xml",
                "required": {
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "xl/workbook.xml",
                },
                "kind": "xlsx",
            },

        "application/vnd.openxmlformats-officedocument.presentationml.presentation":
            {
                "main": "ppt/presentation.xml",
                "required": {
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "ppt/presentation.xml",
                },
                "kind": "pptx",
            },
    }

    EXECUTABLE_EXTENSIONS = {
        ".exe", ".dll", ".bat", ".cmd",
        ".scr", ".vbs", ".ps1", ".jar",
    }

    def __init__(
        self,
        config: SecurityConfig = DEFAULT_CONFIG,
    ):
        super().__init__(config)

        # Reuse the generic ZIP security validator.
        self.zip_validator = ZipSecurityValidator(config)

    # ------------------------------------------
    # Incremental XML validation
    # ------------------------------------------

    def _parse_xml(self, zf, filename, callback=None):

        info = zf.getinfo(filename)

        if info.file_size > self.config.max_xml_size:
            raise ValueError(
                f"XML file exceeds limit: {filename}"
            )

        with zf.open(info) as stream:

            # Maintain a parent stack so processed elements
            # can be detached, rather than only cleared.
            stack = []

            for event, element in ET.iterparse(
                stream,
                events=("start", "end"),
            ):

                if event == "start":
                    stack.append(element)
                    continue

                if callback:
                    callback(element)

                if len(stack) > 1:
                    parent = stack[-2]
                    parent.remove(element)

                element.clear()
                stack.pop()

    # ------------------------------------------
    # Macro detection
    # ------------------------------------------

    def _check_macros(self, names):

        for name in names:

            lower = name.lower()

            if (
                lower.endswith("vbaproject.bin")
                or "/activex/" in lower
            ):

                if self.config.reject_macros:
                    return False

        return True

    # ------------------------------------------
    # Embedded object detection
    # ------------------------------------------

    def _check_embedded_objects(self, names):

        prefixes = (
            "word/embeddings/",
            "xl/embeddings/",
            "ppt/embeddings/",
            "word/activex/",
            "xl/activex/",
            "ppt/activex/",
        )

        found = any(
            name.lower().startswith(prefixes)
            for name in names
        )

        return not (
            found and self.config.reject_embedded_objects
        )

    # ------------------------------------------
    # External relationship detection
    # ------------------------------------------

    def _check_relationships(self, zf, names):

        external_count = 0

        def inspect(element):

            nonlocal external_count

            if not element.tag.endswith("Relationship"):
                return

            target = element.attrib.get("Target", "")
            mode = element.attrib.get("TargetMode", "")

            if mode.lower() == "external":

                external_count += 1

                if self.config.reject_external_relationships:
                    raise ValueError(
                        "External Office relationship detected"
                    )

            if target.lower().startswith(
                ("javascript:", "vbscript:", "file:", "data:")
            ):
                raise ValueError(
                    "Dangerous relationship target"
                )

        for name in names:

            if name.lower().endswith(".rels"):
                self._parse_xml(
                    zf,
                    name,
                    inspect,
                )

        return external_count

    # ------------------------------------------
    # Format-specific checks
    # ------------------------------------------

    def _check_format(self, zf, names, mime_type):

        info = self.FORMATS[mime_type]

        if not info["required"].issubset(names):
            raise ValueError(
                "Invalid OOXML package structure"
            )

        kind = info["kind"]
        main = info["main"]

        counters = {
            "sheets": 0,
            "slides": 0,
            "rows_by_worksheet": {},
        }

        parsed_xml = set()

        # --------------------------------------
        # Workbook / presentation / document XML
        # --------------------------------------

        def inspect_main(element):

            if kind == "xlsx":

                if element.tag.endswith("sheet"):
                    counters["sheets"] += 1

                    if counters["sheets"] > self.config.max_sheets:
                        raise ValueError(
                            "Too many workbook sheets"
                        )

            elif kind == "pptx":

                if element.tag.endswith("sldId"):
                    counters["slides"] += 1

                    if counters["slides"] > self.config.max_slides:
                        raise ValueError(
                            "Too many presentation slides"
                        )

        self._parse_xml(
            zf,
            main,
            inspect_main,
        )

        parsed_xml.add(main)

        # --------------------------------------
        # XLSX worksheet row limits
        # --------------------------------------

        if kind == "xlsx":

            worksheet_files = [
                name for name in names
                if (
                    name.startswith("xl/worksheets/")
                    and name.lower().endswith(".xml")
                    and not name.endswith("/")
                )
            ]

            for worksheet in worksheet_files:

                row_count = 0

                def inspect_rows(element):

                    nonlocal row_count

                    if element.tag.endswith("row"):

                        row_count += 1

                        if row_count > self.config.max_rows_per_sheet:
                            raise ValueError(
                                f"Too many rows in worksheet: {worksheet}"
                            )

                self._parse_xml(
                    zf,
                    worksheet,
                    inspect_rows,
                )

                counters["rows_by_worksheet"][worksheet] = row_count
                parsed_xml.add(worksheet)

        # --------------------------------------
        # Validate all remaining XML parts
        # --------------------------------------

        for name in names:

            if (
                name.lower().endswith((".xml", ".rels"))
                and name not in parsed_xml
                and not name.endswith("/")
            ):

                self._parse_xml(zf, name)

                parsed_xml.add(name)

        return counters

    # ------------------------------------------
    # Main check
    # ------------------------------------------

    def check(
        self,
        file_path,
        mime_type,
        file_size,
    ):

        # 1. Common file validation.
        base = super().check(
            file_path,
            mime_type,
            file_size,
        )

        if not base.passed:
            return base

        checks = base.checks.copy()

        try:

            if mime_type not in self.FORMATS:
                raise ValueError(
                    "Unsupported OOXML format"
                )

            with zipfile.ZipFile(file_path, "r") as zf:

                # ----------------------------------
                # 2. Generic ZIP security validation
                # ----------------------------------

                zip_checks = self.zip_validator.validate(zf)

                checks.update({
                    f"zip_{key}": value
                    for key, value in zip_checks.items()
                })

                names = set(zf.namelist())

                checks["zip_integrity"] = True

                # ----------------------------------
                # 3. Macro detection
                # ----------------------------------

                checks["macros"] = self._check_macros(names)

                # ----------------------------------
                # 4. Embedded object detection
                # ----------------------------------

                checks["embedded_objects"] = (
                    self._check_embedded_objects(names)
                )

                # ----------------------------------
                # 5. OOXML structure and XML validation
                # ----------------------------------

                counters = self._check_format(
                    zf,
                    names,
                    mime_type,
                )

                checks["xml_integrity"] = True
                checks["format_structure"] = True

                # ----------------------------------
                # 6. External relationships
                # ----------------------------------

                external_count = self._check_relationships(
                    zf,
                    names,
                )

                checks["external_relationships"] = (
                    external_count == 0
                    or not self.config.reject_external_relationships
                )

                # ----------------------------------
                # 7. Format limits
                # ----------------------------------

                checks["format_limits"] = True

            # --------------------------------------
            # 8. Final decision
            # --------------------------------------

            failed = [
                key for key, value in checks.items()
                if not value
            ]

            if failed:

                return SecurityReport(
                    result=SecurityCheckResult.QUARANTINE,
                    checks=checks,
                    reason="Office validation failed",
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

            checks["office_validation"] = False

            return SecurityReport(
                result=SecurityCheckResult.QUARANTINE,
                checks=checks,
                reason=f"Office inspection failed: {exc}",
                file_path=file_path,
                mime_type=mime_type,
                file_size=file_size,
                sha256=base.sha256,
            )