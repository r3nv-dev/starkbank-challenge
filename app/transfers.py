"""Transfers the received invoice amount (minus fees) to the Stark Bank S.A. account."""
import logging

import starkbank
from starkbank.error import InputErrors

logger = logging.getLogger(__name__)

DESTINATION = {
    "bank_code": "20018183",
    "branch_code": "0001",
    "account_number": "6341320293482496",
    "name": "Stark Bank S.A.",
    "tax_id": "20.018.183/0001-80",
    "account_type": "payment",
}


def net_amount(invoice) -> int:
    """Received amount minus the fee Stark Bank charged, in cents."""
    return invoice.amount - (getattr(invoice, "fee", 0) or 0)


def _looks_like_duplicate_external_id(error: InputErrors) -> bool:
    # Defensive: in the sandbox a duplicate external_id is NOT rejected here —
    # transfer.create returns 200 and the transfer fails asynchronously with
    # "Duplicated transfer" (docs/starkbank-findings.md #4), so this branch does
    # not fire there. Kept in case the API ever rejects duplicates synchronously
    # with a structured InputErrors, as its docs imply.
    for item in getattr(error, "errors", []):
        code = str(getattr(item, "code", item)).lower()
        message = str(getattr(item, "message", "")).lower()
        if "external" in code or "external" in message:
            return True
    return False


def transfer_invoice_credit(invoice) -> starkbank.Transfer | None:
    """Send the invoice's net amount to the destination account.

    Uses the invoice id as external_id so the API rejects accidental
    duplicates even if the same webhook event is processed twice.
    """
    amount = net_amount(invoice)
    if amount <= 0:
        logger.warning("invoice %s has no net amount to transfer (fee >= amount)", invoice.id)
        return None

    try:
        (transfer,) = starkbank.transfer.create([
            starkbank.Transfer(
                amount=amount,
                external_id=f"invoice-{invoice.id}",
                tags=["challenge"],
                **DESTINATION,
            )
        ])
    except InputErrors as error:
        if _looks_like_duplicate_external_id(error):
            logger.info("transfer already exists for invoice %s; treating as processed", invoice.id)
            return None
        raise
    logger.info("created transfer id=%s amount=%s for invoice=%s", transfer.id, amount, invoice.id)
    return transfer
