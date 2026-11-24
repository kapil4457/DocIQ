"""No-op event publisher — default when no queue is configured."""

import logging
from events.publisher import DocumentReadyEvent, EventPublisher

logger = logging.getLogger("app.events")


class NoopEventPublisher(EventPublisher):
    """Default publisher that does nothing — used when no queue is configured."""

    def publish_document_ready(self, event: DocumentReadyEvent) -> None:
        logger.debug(
            "Event publishing disabled (noop); would publish",
            extra={"extra_data": {"event": event.__dict__}},
        )