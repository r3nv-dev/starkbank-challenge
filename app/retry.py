"""Retry job for transfers that failed asynchronously.

The API can accept a Transfer and fail it moments later (observed in the
sandbox: an opaque 'Duplicated transfer', and 'Target account is blocked'
while the challenge's destination account was temporarily blocked). By that
point the webhook event is already marked processed, so no redelivery will
recreate the payout. This job sweeps the account's transfers and recreates
failed ones with a fresh, deterministic external_id (invoice-<id>-r<n>).

Double-payout safety: an invoice is retried only when it has NO transfer in a
live or successful state — any status other than "failed"/"canceled" counts as
alive, so unknown states are never retried past. The deterministic external_id
also caps concurrent sweeps: two racing sweeps compute the same id and the API
rejects the second while the first is alive.

Run: python -m app.retry
"""
import logging
import re
from collections import defaultdict

import starkbank

from app.transfers import DESTINATION

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
_DEAD_STATUSES = {"failed", "canceled"}
_EXTERNAL_ID = re.compile(r"^(?P<base>invoice-.+?)(?:-r(?P<attempt>\d+))?$")


def retry_failed_transfers() -> int:
    """Recreate one fresh transfer per invoice whose attempts all failed."""
    by_invoice = defaultdict(list)
    for transfer in starkbank.transfer.query(tags=["challenge"]):
        match = _EXTERNAL_ID.match(transfer.external_id or "")
        if match:
            by_invoice[match.group("base")].append(transfer)

    retried = 0
    for base, transfers in by_invoice.items():
        if any(t.status not in _DEAD_STATUSES for t in transfers):
            continue  # a live or successful transfer exists; never double-pay
        if len(transfers) >= MAX_ATTEMPTS:
            logger.warning("giving up on %s after %s failed attempts", base, len(transfers))
            continue
        attempt = len(transfers) + 1
        latest = max(transfers, key=lambda t: t.id)
        (created,) = starkbank.transfer.create([
            starkbank.Transfer(
                amount=latest.amount,
                external_id=f"{base}-r{attempt}",
                tags=["challenge"],
                **DESTINATION,
            )
        ])
        logger.info("retried %s attempt=%s transfer id=%s amount=%s",
                    base, attempt, created.id, created.amount)
        retried += 1

    logger.info("retry sweep done: %s transfers recreated", retried)
    return retried


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from app.config import setup_starkbank
    setup_starkbank()
    retry_failed_transfers()
