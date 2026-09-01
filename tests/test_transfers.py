from types import SimpleNamespace
from unittest.mock import patch

from app.transfers import DESTINATION, transfer_invoice_credit


def make_invoice(amount=10_000, fee=118, id="123"):
    return SimpleNamespace(amount=amount, fee=fee, id=id)


@patch("app.transfers.starkbank.transfer.create", side_effect=lambda batch: batch)
def test_transfer_deducts_fee(mock_create):
    transfer = transfer_invoice_credit(make_invoice(amount=10_000, fee=118))
    assert transfer.amount == 9_882


@patch("app.transfers.starkbank.transfer.create", side_effect=lambda batch: batch)
def test_transfer_targets_starkbank_account(mock_create):
    transfer = transfer_invoice_credit(make_invoice())
    assert transfer.bank_code == DESTINATION["bank_code"]
    assert transfer.account_number == DESTINATION["account_number"]
    assert transfer.tax_id == DESTINATION["tax_id"]
    assert transfer.account_type == DESTINATION["account_type"]


@patch("app.transfers.starkbank.transfer.create", side_effect=lambda batch: batch)
def test_transfer_uses_invoice_id_as_external_id(mock_create):
    transfer = transfer_invoice_credit(make_invoice(id="999"))
    assert transfer.external_id == "invoice-999"


@patch("app.transfers.starkbank.transfer.create")
def test_no_transfer_when_fee_exceeds_amount(mock_create):
    assert transfer_invoice_credit(make_invoice(amount=100, fee=200)) is None
    mock_create.assert_not_called()


@patch("app.transfers.starkbank.transfer.create", side_effect=lambda batch: batch)
def test_missing_fee_treated_as_zero(mock_create):
    invoice = SimpleNamespace(amount=5_000, id="1", fee=None)
    transfer = transfer_invoice_credit(invoice)
    assert transfer.amount == 5_000
