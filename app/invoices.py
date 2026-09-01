"""Invoice issuing: batches of 8-12 invoices to random people."""
import logging
import random

import starkbank

from app.people import random_person

logger = logging.getLogger(__name__)

MIN_INVOICES = 8
MAX_INVOICES = 12
MIN_AMOUNT_CENTS = 500  # R$ 5.00
MAX_AMOUNT_CENTS = 50_000  # R$ 500.00


def build_random_invoice() -> starkbank.Invoice:
    person = random_person()
    return starkbank.Invoice(
        amount=random.randint(MIN_AMOUNT_CENTS, MAX_AMOUNT_CENTS),
        name=person.name,
        tax_id=person.tax_id,
        tags=["challenge"],
    )


def issue_random_invoices() -> list:
    count = random.randint(MIN_INVOICES, MAX_INVOICES)
    invoices = starkbank.invoice.create([build_random_invoice() for _ in range(count)])
    for invoice in invoices:
        logger.info("issued invoice id=%s amount=%s", invoice.id, invoice.amount)
    return invoices
