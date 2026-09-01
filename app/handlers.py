"""Business handler shared by the webhook receiver and the reconciliation job."""
import logging

from app.events import EventStore
from app.transfers import transfer_invoice_credit

logger = logging.getLogger(__name__)


def handle_event(event, store: EventStore) -> str:
    """Process one Stark Bank event; returns "ok" | "duplicate" | "ignored".

    Only "credited" invoice logs trigger a transfer: "credited" is the moment
    the money lands in the account ("paid" precedes it) — reacting to both
    would double-pay. The event is marked as processed only AFTER the transfer
    succeeds, so a failure leaves it unmarked and Stark Bank's redelivery
    retries it; a crash between transfer and mark cannot double-pay because
    the Transfer external_id is rejected by the API on the second attempt.
    """
    if event.subscription != "invoice" or getattr(event.log, "type", None) != "credited":
        logger.info("ignoring event id=%s subscription=%s type=%s",
                    event.id, event.subscription, getattr(event.log, "type", None))
        return "ignored"
    if store.is_processed(event.id):
        logger.info("skipping duplicate event id=%s", event.id)
        return "duplicate"
    transfer_invoice_credit(event.log.invoice)
    store.mark_processed(event.id)
    return "ok"
