"""Factory for creating event publishers based on environment configuration."""

import json
import logging
import os
from events.publisher import EventPublisher
from events.strategies import (
    NoopEventPublisher,
    HttpWebhookEventPublisher,
    CloudflareQueuesEventPublisher,
)

logger = logging.getLogger("app.events")


def create_event_publisher() -> EventPublisher:
    """Factory: reads env and returns the configured publisher.

    Config:
      EVENT_PUBLISHER_TYPE: "noop" | "http" | "cloudflare-queues" (default: "noop")

      # For type="http":
      EVENT_WEBHOOK_URL: required
      EVENT_WEBHOOK_TIMEOUT: seconds (default: 5)
      EVENT_WEBHOOK_HEADERS: JSON object (optional)

      # For type="cloudflare-queues":
      CF_QUEUE_ACCOUNT_ID: required
      CF_QUEUE_ID: required
      CF_API_TOKEN: required
      CF_QUEUE_TIMEOUT: seconds (default: 10)
    """
    publisher_type = os.getenv("EVENT_PUBLISHER_TYPE", "noop").lower()

    if publisher_type == "http":
        url = os.getenv("EVENT_WEBHOOK_URL")
        if not url:
            logger.warning("EVENT_PUBLISHER_TYPE=http but EVENT_WEBHOOK_URL not set; falling back to noop")
            return NoopEventPublisher()
        timeout = float(os.getenv("EVENT_WEBHOOK_TIMEOUT", "5"))
        headers = {}
        raw_headers = os.getenv("EVENT_WEBHOOK_HEADERS")
        if raw_headers:
            try:
                headers = json.loads(raw_headers)
            except Exception:
                logger.warning("EVENT_WEBHOOK_HEADERS invalid JSON; ignoring")
        return HttpWebhookEventPublisher(url, timeout, headers)

    if publisher_type == "cloudflare-queues":
        account_id = os.getenv("CF_QUEUE_ACCOUNT_ID")
        queue_id = os.getenv("CF_QUEUE_ID")
        api_token = os.getenv("CF_API_TOKEN")
        if not (account_id and queue_id and api_token):
            logger.warning(
                "EVENT_PUBLISHER_TYPE=cloudflare-queues but CF_QUEUE_ACCOUNT_ID/CF_QUEUE_ID/CF_API_TOKEN "
                "not all set; falling back to noop"
            )
            return NoopEventPublisher()
        timeout = float(os.getenv("CF_QUEUE_TIMEOUT", "10"))
        return CloudflareQueuesEventPublisher(account_id, queue_id, api_token, timeout)

    return NoopEventPublisher()