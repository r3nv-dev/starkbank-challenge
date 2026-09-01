from unittest.mock import patch

from app.invoices import (
    MAX_AMOUNT_CENTS,
    MAX_INVOICES,
    MIN_AMOUNT_CENTS,
    MIN_INVOICES,
    build_random_invoice,
    issue_random_invoices,
)


def test_build_random_invoice_within_bounds():
    for _ in range(100):
        invoice = build_random_invoice()
        assert MIN_AMOUNT_CENTS <= invoice.amount <= MAX_AMOUNT_CENTS
        assert invoice.name
        assert invoice.tax_id


@patch("app.invoices.starkbank.invoice.create", side_effect=lambda batch: batch)
def test_issue_random_invoices_batch_size(mock_create):
    for _ in range(50):
        invoices = issue_random_invoices()
        assert MIN_INVOICES <= len(invoices) <= MAX_INVOICES
    assert mock_create.call_count == 50
