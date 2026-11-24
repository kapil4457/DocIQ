from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SecurityCheckResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    QUARANTINE = "quarantine"


@dataclass
class SecurityReport:

    result: SecurityCheckResult

    checks: dict[str, bool] = field(default_factory=dict)

    reason: Optional[str] = None
    details: Optional[str] = None

    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    sha256: Optional[str] = None

    @property
    def passed(self):
        return self.result == SecurityCheckResult.PASS

    @property
    def failed_checks(self):
        return [
            key
            for key, value in self.checks.items()
            if not value
        ]