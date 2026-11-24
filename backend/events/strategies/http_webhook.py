"""HTTP webhook event publisher — generic JSON POST endpoint."""

import json
import logging
import urllib.request
from events.publisher import DocumentReadyEvent, EventPublisher

logger = logging.getLogger("app.events")


class HttpWebhookEventPublisher(EventPublisher):
    """Generic HTTP webhook publisher — works with Cloudflare Queues HTTP pull,
    SQS HTTP endpoint, Kafka REST proxy, or any JSON webhook."""

    def __init__(
        self,
        endpoint_url: str,
        timeout_seconds: float = 5.0,
        headers: dict[str, str] | None = None,
    ):
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds
        self.headers = {"Content-Type": "application/json", **(headers or {})}

    def publish_document_ready(self, event: DocumentReadyEvent) -> None:
        payload = event.to_json().encode("utf-8")
        req = urllib.request.Request(
            self.endpoint_url,
            data=payload,
            headers=self.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status >= 300:
                    logger.warning(
                        "Event webhook returned non-2xx",
                        extra={"extra_data": {"status": resp.status, "event": event.__dict__}},
                    )
                else:
                    logger.info(
                        "Document ready event published",
                        extra={"extra_data": {"documentVersionId": event.document_version_id}},
                    )
        except Exception as exc:
            logger.error(
                "Failed to publish document ready event",
                extra={"extra_data": {"event": event.__dict__, "error": str(exc)}},
                exc_info=True,
            )