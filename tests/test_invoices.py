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


@patch("app.invoices.starkbank.invoice.create", side_effect=lambda batch: batch)
def test_issue_logging_has_no_pii(mock_create, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="app.invoices"):
        invoices = issue_random_invoices()
    for invoice in invoices:
        assert invoice.name not in caplog.text
        assert invoice.tax_id not in caplog.text
