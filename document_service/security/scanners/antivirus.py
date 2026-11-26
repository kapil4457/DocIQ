from dataclasses import dataclass
from enum import Enum
import os

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
        shared_mount_host: str | None = None,
        shared_mount_container: str = "/shared",
    ):

        self.config = config
        self.host = host
        self.port = port
        self.timeout = timeout
        # Host-side staging dir; when None, no path translation is done
        # (correct for a natively-installed ClamAV daemon).
        self.shared_mount_host = shared_mount_host
        self.shared_mount_container = shared_mount_container

    def _translate_path(self, host_path: str) -> str:
        """Translate Windows host path to container path (Docker deployment)."""
        if self.shared_mount_host and host_path.startswith(self.shared_mount_host):
            rel_path = os.path.relpath(host_path, self.shared_mount_host)
            return os.path.join(self.shared_mount_container, rel_path).replace("\\", "/")
        return host_path

    def scan(self, file_path: str) -> AntivirusReport:

        # Translate path for ClamAV in Docker
        container_path = self._translate_path(file_path)

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

            # Scan file using container path.
            result = client.scan(container_path)

            if not result:
                raise RuntimeError("No scan result returned")

            file_result = result.get(container_path)

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