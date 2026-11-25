"""
HTML security check.

Validates HTML documents without executing or rendering them:
  - Encoding / structural integrity (via a tolerant parser)
  - Element and nesting limits (resource-exhaustion guard)
  - Active-content rejection: <script>, <iframe>, <object>, <embed>,
    <applet>, javascript: URLs, and inline event-handler attributes
  - Safe parsing via defusedxml-style hardening (no entity expansion)
"""

import re

from html.parser import HTMLParser

from .base import FileSecurityCheck
from document_service.security.models import SecurityReport, SecurityCheckResult
from document_service.security.config import DEFAULT_CONFIG, SecurityConfig


# Elements that can execute code or fetch remote resources.
ACTIVE_CONTENT_TAGS = {
    "script",
    "iframe",
    "object",
    "embed",
    "applet",
    "frame",
    "frameset",
    "base",
}

# URL schemes that can execute code from a hyperlink/resource reference.
DANGEROUS_URL_SCHEMES = re.compile(
    r"^\s*(javascript|vbscript|data|file):",
    re.IGNORECASE,
)

# Attributes that hold URLs on common elements.
URL_ATTRIBUTES = {"href", "src", "action", "formaction", "xlink:href", "poster"}

# Inline event handlers: on*
EVENT_ATTR_PATTERN = re.compile(r"^on[a-z]+$", re.IGNORECASE)

# Dangerous style constructs (expression() was IE-specific but kept as policy).
DANGEROUS_STYLE = re.compile(r"expression\s*\(|javascript\s*:", re.IGNORECASE)


class _HTMLAudit(HTMLParser):
    """Tolerant, non-executing HTML walker that collects security signals."""

    def __init__(self, config: SecurityConfig):
        super().__init__(convert_charrefs=True)
        self.config = config

        self.tag_count = 0
        self.max_depth = 0
        self.depth = 0

        self.active_tags = set()
        self.dangerous_urls = set()
        self.event_handler_attrs = set()
        self.dangerous_styles = False

        self.parse_error = None

    # -- element bookkeeping -------------------------------------------------

    def handle_starttag(self, tag, attrs):
        self.tag_count += 1
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)

        if self.tag_count > self.config.max_html_tag_count:
            self.parse_error = "Too many HTML elements"
            self.reset()

        if self.max_depth > self.config.max_html_nesting_depth:
            self.parse_error = "HTML nesting too deep"
            self.reset()

        lower = tag.lower()

        if lower in ACTIVE_CONTENT_TAGS:
            self.active_tags.add(lower)

        for name, value in attrs:
            attr_lower = name.lower()
            value = value or ""

            if EVENT_ATTR_PATTERN.match(attr_lower):
                self.event_handler_attrs.add(attr_lower)

            if attr_lower in URL_ATTRIBUTES and DANGEROUS_URL_SCHEMES.match(value):
                self.dangerous_urls.add(f"{attr_lower}={value[:60]}")

            if attr_lower == "style" and DANGEROUS_STYLE.search(value):
                self.dangerous_styles = True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.depth -= 1

    def handle_endtag(self, tag):
        self.depth = max(0, self.depth - 1)

    def close(self):
        super().close()


class HtmlSecurityCheck(FileSecurityCheck):
    """Security validation for text/html documents."""

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

        try:
            # HTML is text; hard-reject invalid UTF-8 before parsing.
            with open(file_path, "r", encoding="utf-8", errors="strict") as f:
                content = f.read()

            checks["encoding"] = True

            auditor = _HTMLAudit(self.config)
            try:
                auditor.feed(content)
                auditor.close()
            except Exception as exc:
                checks["html_parseable"] = False
                reasons.append(f"HTML parse failed: {exc}")

            if auditor.parse_error:
                checks["html_limits"] = False
                reasons.append(auditor.parse_error)

            checks["active_content"] = (
                not (self.config.reject_html_scripts and auditor.active_tags)
            )
            if auditor.active_tags and self.config.reject_html_scripts:
                reasons.append(
                    "Active content elements present: "
                    + ", ".join(sorted(auditor.active_tags))
                )

            checks["dangerous_urls"] = not auditor.dangerous_urls
            if auditor.dangerous_urls:
                reasons.append(
                    "Dangerous URL schemes: "
                    + ", ".join(sorted(auditor.dangerous_urls))
                )

            checks["event_handlers"] = not auditor.event_handler_attrs
            if auditor.event_handler_attrs:
                reasons.append(
                    "Inline event handlers present: "
                    + ", ".join(sorted(auditor.event_handler_attrs))
                )

            checks["styles"] = not auditor.dangerous_styles
            if auditor.dangerous_styles:
                reasons.append("Dangerous style expression detected")

        except UnicodeDecodeError:
            checks["encoding"] = False
            reasons.append("Invalid UTF-8 encoding")

        except Exception as exc:
            checks["parseable"] = False
            reasons.append(str(exc))

        failed = [key for key, value in checks.items() if not value]

        if failed:
            critical = {"encoding", "parseable"}
            result = (
                SecurityCheckResult.QUARANTINE
                if critical.intersection(failed)
                else SecurityCheckResult.FAIL
            )

            return SecurityReport(
                result=result,
                checks=checks,
                reason="; ".join(reasons) or "HTML validation failed",
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
