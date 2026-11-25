from dataclasses import dataclass
from enum import Enum

import clamd

from document_service.security.config import DEFAULT_CONFIG, SecurityConfig


class AntivirusStatus(str, Enum):

    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"


@dataclass
class AntivirusReport:

    status: AntivirusStatus

    signature: str | None = None

    reason: str | None = None


class ClamAVScanner:

    def __init__(
        self,
        config: SecurityConfig = DEFAULT_CONFIG,
        host: str = "127.0.0.1",
        port: int = 3310,
        timeout: int = 120,
    ):

        self.config = config
        self.host = host
        self.port = port
        self.timeout = timeout

    def scan(self, file_path: str) -> AntivirusReport:

        try:

            client = clamd.ClamdNetworkSocket(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
            )

            # Check daemon connectivity.
            client.ping()

            # Check antivirus engine availability.
            version = client.version()

            if not version:
                raise RuntimeError("ClamAV version unavailable")

            # Scan file.
            result = client.scan(file_path)

            if not result:
                raise RuntimeError("No scan result returned")

            file_result = result.get(file_path)

            if not file_result:
                raise RuntimeError(
                    "File missing from antivirus scan response"
                )

            status, signature = file_result

            if status == "OK":

                return AntivirusReport(
                    status=AntivirusStatus.CLEAN,
                )

            if status == "FOUND":

                return AntivirusReport(
                    status=AntivirusStatus.INFECTED,
                    signature=signature,
                    reason="Malware detected",
                )

            return AntivirusReport(
                status=AntivirusStatus.ERROR,
                reason=f"Unexpected scanner response: {status}",
            )

        except Exception as exc:

            return AntivirusReport(
                status=AntivirusStatus.ERROR,
                reason=str(exc),
            )