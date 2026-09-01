from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.events import InMemoryEventStore
from app.handlers import handle_event


def make_event(id="evt-1", subscription="invoice", log_type="credited"):
    invoice = SimpleNamespace(amount=10_000, fee=118, id="inv-1")
    return SimpleNamespace(
        id=id, subscription=subscription, log=SimpleNamespace(type=log_type, invoice=invoice)
    )


@pytest.fixture
def store():
    return InMemoryEventStore()


@patch("app.handlers.transfer_invoice_credit")
def test_credited_event_transfers_and_marks_processed(mock_transfer, store):
    assert handle_event(make_event(), store) == "ok"
    mock_transfer.assert_called_once()
    assert store.is_processed("evt-1")


@patch("app.handlers.transfer_invoice_credit")
def test_duplicate_event_does_not_transfer_again(mock_transfer, store):
    handle_event(make_event(), store)
    assert handle_event(make_event(), store) == "duplicate"
    assert mock_transfer.call_count == 1


@patch("app.handlers.transfer_invoice_credit")
def test_paid_log_is_ignored_without_marking(mock_transfer, store):
    assert handle_event(make_event(log_type="paid"), store) == "ignored"
    mock_transfer.assert_not_called()
    assert not store.is_processed("evt-1")


@patch("app.handlers.transfer_invoice_credit")
def test_other_subscription_is_ignored(mock_transfer, store):
    assert handle_event(make_event(subscription="transfer"), store) == "ignored"
    mock_transfer.assert_not_called()


@patch("app.handlers.transfer_invoice_credit", side_effect=RuntimeError("api down"))
def test_failed_transfer_leaves_event_unprocessed(mock_transfer, store):
    with pytest.raises(RuntimeError):
        handle_event(make_event(), store)
    assert not store.is_processed("evt-1")  # redelivery da Stark vai reprocessar
