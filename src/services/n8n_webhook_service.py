import logging
from threading import Thread

import requests

from src.core.config import N8N_RESERVATION_WEBHOOK_URL


logger = logging.getLogger(__name__)


class N8nWebhookService:
    """Dispatches backend-owned events to n8n webhooks."""

    WEBHOOK_URL = N8N_RESERVATION_WEBHOOK_URL
    TIMEOUT_SECONDS = 5

    @classmethod
    def trigger_reservation_created(cls, payload: dict) -> None:
        """Trigger the reservation-created automation without blocking the request."""
        if not cls.WEBHOOK_URL:
            logger.info("N8N reservation webhook URL is not configured")
            return

        thread = Thread(
            target=cls._post_reservation_created,
            args=(payload,),
            daemon=True,
        )
        thread.start()

    @classmethod
    def _post_reservation_created(cls, payload: dict) -> None:
        try:
            response = requests.post(
                cls.WEBHOOK_URL,
                json=payload,
                timeout=cls.TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            logger.info(
                "N8N reservation webhook triggered successfully: reservation_id=%s",
                payload.get("reservation_id"),
            )
        except requests.RequestException:
            logger.exception(
                "N8N reservation webhook failed: reservation_id=%s",
                payload.get("reservation_id"),
            )
