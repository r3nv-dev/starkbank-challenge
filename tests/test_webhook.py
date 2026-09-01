from types import SimpleNamespace
from unittest.mock import patch

import starkbank
from fastapi.testclient import TestClient

from app import webhook_app

client = TestClient(webhook_app.app)

HEADERS = {"Digital-Signature": "fake-signature"}


def make_event(id="evt-1", subscription="invoice", log_type="credited"):
    invoice = SimpleNamespace(amount=10_000, fee=118, id="inv-1")
    return SimpleNamespace(
        id=id, subscription=subscription, log=SimpleNamespace(type=log_type, invoice=invoice)
    )


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


@patch("app.handlers.transfer_invoice_credit")
@patch("app.webhook_app.starkbank.event.parse")
def test_credited_invoice_triggers_transfer(mock_parse, mock_transfer):
    mock_parse.return_value = make_event(id="evt-credited")
    response = client.post("/webhook", content=b"{}", headers=HEADERS)
    assert response.status_code == 200
    mock_transfer.assert_called_once_with(mock_parse.return_value.log.invoice)


@patch("app.handlers.transfer_invoice_credit")
@patch("app.webhook_app.starkbank.event.parse")
def test_non_credited_event_is_ignored(mock_parse, mock_transfer):
    mock_parse.return_value = make_event(id="evt-created", log_type="created")
    response = client.post("/webhook", content=b"{}", headers=HEADERS)
    assert response.status_code == 200
    mock_transfer.assert_not_called()


@patch("app.handlers.transfer_invoice_credit")
@patch("app.webhook_app.starkbank.event.parse")
def test_duplicate_event_is_not_processed_twice(mock_parse, mock_transfer):
    mock_parse.return_value = make_event(id="evt-dup")
    first = client.post("/webhook", content=b"{}", headers=HEADERS)
    second = client.post("/webhook", content=b"{}", headers=HEADERS)
    assert first.json() == {"status": "ok"}
    assert second.json() == {"status": "duplicate"}
    assert mock_transfer.call_count == 1


@patch("app.webhook_app.starkbank.event.parse")
def test_invalid_signature_is_rejected(mock_parse):
    mock_parse.side_effect = starkbank.error.InvalidSignatureError("bad signature")
    response = client.post("/webhook", content=b"{}", headers=HEADERS)
    assert response.status_code == 400
