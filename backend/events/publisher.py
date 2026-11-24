"""Event publisher protocol and event types."""

from dataclasses import dataclass
from typing import Protocol
import json


@dataclass(frozen=True)
class DocumentReadyEvent:
    """Published when a document version becomes available for processing."""
    document_version_id: str
    user_id: str
    document_id: str
    organization_id: str
    workspace_id: str | None
    object_key: str
    file_size: int
    media_type: str
    sha256_hash: str | None
    published_at: str  # ISO 8601 UTC

    def to_json(self) -> str:
        return json.dumps(self.__dict__, separators=(",", ":"))


class EventPublisher(Protocol):
    """Publish document-ready events to a downstream queue/stream."""

    def publish_document_ready(self, event: DocumentReadyEvent) -> None:
        """Fire-and-forget publish; logs failures but never raises."""
        ...