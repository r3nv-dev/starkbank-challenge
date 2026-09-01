"""Transfers the received invoice amount (minus fees) to the Stark Bank S.A. account."""
import logging

import starkbank

logger = logging.getLogger(__name__)

DESTINATION = {
    "bank_code": "20018183",
    "branch_code": "0001",
    "account_number": "6341320293482496",
    "name": "Stark Bank S.A.",
    "tax_id": "20.018.183/0001-80",
    "account_type": "payment",
}


def transfer_invoice_credit(invoice) -> starkbank.Transfer | None:
    """Send the invoice's net amount to the destination account.

    Uses the invoice id as external_id so the API rejects accidental
    duplicates even if the same webhook event is processed twice.
    """
    net_amount = invoice.amount - (getattr(invoice, "fee", 0) or 0)
    if net_amount <= 0:
        logger.warning("invoice %s has no net amount to transfer (fee >= amount)", invoice.id)
        return None

    (transfer,) = starkbank.transfer.create([
        starkbank.Transfer(
            amount=net_amount,
            external_id=f"invoice-{invoice.id}",
            tags=["challenge"],
            **DESTINATION,
        )
    ])
    logger.info("created transfer id=%s amount=%s for invoice=%s", transfer.id, net_amount, invoice.id)
    return transfer
