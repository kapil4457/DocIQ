"""Cloudflare Queues native publisher using the REST API."""

import json
import logging
import urllib.error
import urllib.request
from events.publisher import DocumentReadyEvent, EventPublisher

logger = logging.getLogger("app.events")


class CloudflareQueuesEventPublisher(EventPublisher):
    """Cloudflare Queues native publisher using the REST API.
    Docs: https://developers.cloudflare.com/queues/configuration/json-api/
    POST https://api.cloudflare.com/client/v4/accounts/{account_id}/queues/{queue_id}/messages
    Body: [{"body": "<base64-json>"}]
    """

    def __init__(
        self,
        account_id: str,
        queue_id: str,
        api_token: str,
        timeout_seconds: float = 10.0,
    ):
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/queues/{queue_id}/messages"
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds

    def publish_document_ready(self, event: DocumentReadyEvent) -> None:
        # Cloudflare Queues expects a single message with JSON body (no base64)
        payload = json.dumps({"body": event.__dict__}).encode("utf-8")

        req = urllib.request.Request(
            self.base_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                if not resp_data.get("success"):
                    errors = resp_data.get("errors", [])
                    logger.warning(
                        "Cloudflare Queues publish failed",
                        extra={"extra_data": {"errors": errors, "event": event.__dict__}},
                    )
                else:
                    logger.info(
                        "Document ready event published to Cloudflare Queues",
                        extra={"extra_data": {"documentVersionId": event.document_version_id}},
                    )
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8") if exc.fp else "no response body"
            logger.error(
                "Cloudflare Queues HTTP error",
                extra={"extra_data": {
                    "status": exc.code,
                    "reason": exc.reason,
                    "body": error_body,
                    "event": event.__dict__,
                }},
                exc_info=True,
            )
        except Exception as exc:
            logger.error(
                "Failed to publish document ready event to Cloudflare Queues",
                extra={"extra_data": {"event": event.__dict__, "error": str(exc)}},
                exc_info=True,
            )