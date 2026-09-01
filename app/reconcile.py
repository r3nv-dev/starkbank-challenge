"""Reconciliation for undelivered webhook events.

Stark Bank retries webhook delivery at most three times (5min, 30min, 120min
after the first attempt) and then gives up. The official docs recommend
periodically fetching undelivered events and marking them delivered once
processed — this job does exactly that, reusing the webhook's handler.
Run: python -m app.reconcile
"""
import logging

import starkbank

from app.config import load_settings, setup_starkbank
from app.events import EventStore, create_event_store
from app.handlers import handle_event

logger = logging.getLogger(__name__)


def reconcile(store: EventStore) -> int:
    processed = 0
    for event in starkbank.event.query(is_delivered=False):
        try:
            handle_event(event, store)
        except Exception:
            logger.exception("failed to reconcile event id=%s; leaving undelivered", event.id)
            continue
        starkbank.event.update(event.id, is_delivered=True)
        processed += 1
    logger.info("reconciliation done: %s events processed", processed)
    return processed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    setup_starkbank(settings)
    reconcile(create_event_store(settings.database_url))
