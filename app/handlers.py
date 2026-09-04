"""Business handler shared by the webhook receiver and the reconciliation job."""
import logging

from app.events import EventStore
from app.transfers import transfer_invoice_credit

logger = logging.getLogger(__name__)


def handle_event(event, store: EventStore) -> str:
    """Process one Stark Bank event; returns "ok" | "duplicate" | "ignored".

    Only "credited" invoice logs trigger a transfer: "credited" is the moment
    the money lands in the account ("paid" precedes it) — reacting to both
    would double-pay. The event is marked as processed only AFTER
    transfer_invoice_credit returns, so a failure leaves it unmarked and Stark
    Bank's redelivery retries it.

    Double-payout safety comes from two layers: the local processed-events
    store (primary), and Stark's own rejection of a reused Transfer external_id
    (backstop, in case the store is lost). Note the backstop is ASYNCHRONOUS in
    the sandbox: a duplicate external_id is accepted by transfer.create and only
    later fails with "Duplicated transfer" (see docs/starkbank-findings.md #4),
    so it prevents a second payout but does not raise here. Transfers that fail
    asynchronously are recovered by the separate retry job (app/retry.py).
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
