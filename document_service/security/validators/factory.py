"""Factory for creating file security checkers based on MIME type."""

from .base import FileSecurityCheck
from .pdf import PDFSecurityCheck
from .office import OfficeSecurityCheck
from .text import TextSecurityCheck
from .csv import CsvSecurityCheck


class SecurityCheckerFactory:
    """Factory for creating appropriate security checkers based on MIME type."""

    # MIME type to checker class mapping
    _CHECKER_MAP = {
        "application/pdf": PDFSecurityCheck,
        "application/msword": OfficeSecurityCheck,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": OfficeSecurityCheck,
        "application/vnd.ms-excel": OfficeSecurityCheck,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": OfficeSecurityCheck,
        "application/vnd.ms-powerpoint": OfficeSecurityCheck,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": OfficeSecurityCheck,
        "text/plain": TextSecurityCheck,
        "text/markdown": TextSecurityCheck,
        "text/csv": CsvSecurityCheck,
    }

    @classmethod
    def get_checker(cls, mime_type: str) -> FileSecurityCheck:
        """Get the appropriate security checker for the given MIME type."""
        checker_class = cls._CHECKER_MAP.get(mime_type)
        if checker_class is None:
            # Default to base checker for unknown types
            from .base import FileSecurityCheck
            return FileSecurityCheck()
        return checker_class()

    @classmethod
    def get_supported_mime_types(cls) -> list[str]:
        """Get list of supported MIME types."""
        return list(cls._CHECKER_MAP.keys())

    @classmethod
    def is_supported(cls, mime_type: str) -> bool:
        """Check if MIME type is supported."""
        return mime_type in cls._CHECKER_MAP


def run_security_check(file_path: str, mime_type: str, file_size: int):
    """Convenience function to run security check on a file."""
    checker = SecurityCheckerFactory.get_checker(mime_type)
    return checker.check(file_path, mime_type, file_size)