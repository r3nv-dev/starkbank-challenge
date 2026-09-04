"""Tests for the failed-transfer retry job.

Sandbox reality check (2026-09-04): a Transfer can be accepted by the API and
then fail asynchronously (e.g. 'Target account is blocked', or an opaque
'Duplicated transfer'). By then the webhook event is already marked processed,
so nothing retries the payout. The retry job sweeps failed transfers and
recreates them with a fresh, deterministic external_id — but only when the
invoice has no live or successful transfer, so a double payout stays impossible.
"""
from types import SimpleNamespace
from unittest.mock import patch

from app.retry import retry_failed_transfers


def make_transfer(invoice_id, status, attempt=None, amount=1000):
    suffix = f"-r{attempt}" if attempt else ""
    return SimpleNamespace(
        id=f"tr-{invoice_id}{suffix}",
        status=status,
        amount=amount,
        external_id=f"invoice-{invoice_id}{suffix}",
    )


@patch("app.retry.starkbank.transfer")
def test_retries_failed_transfer_with_fresh_external_id(mock_transfer):
    mock_transfer.query.return_value = iter([make_transfer("inv1", "failed", amount=28738)])
    mock_transfer.create.side_effect = lambda batch: batch

    assert retry_failed_transfers() == 1
    (batch,) = mock_transfer.create.call_args[0]
    (transfer,) = batch
    assert transfer.external_id == "invoice-inv1-r2"
    assert transfer.amount == 28738


@patch("app.retry.starkbank.transfer")
def test_does_not_retry_when_a_live_transfer_exists(mock_transfer):
    mock_transfer.query.return_value = iter([
        make_transfer("inv1", "failed"),
        make_transfer("inv1", "processing", attempt=2),
    ])

    assert retry_failed_transfers() == 0
    mock_transfer.create.assert_not_called()


@patch("app.retry.starkbank.transfer")
def test_does_not_retry_when_a_transfer_succeeded(mock_transfer):
    mock_transfer.query.return_value = iter([
        make_transfer("inv1", "failed"),
        make_transfer("inv1", "success", attempt=2),
    ])

    assert retry_failed_transfers() == 0
    mock_transfer.create.assert_not_called()


@patch("app.retry.starkbank.transfer")
def test_attempt_counter_increments_from_existing_attempts(mock_transfer):
    mock_transfer.query.return_value = iter([
        make_transfer("inv1", "failed"),
        make_transfer("inv1", "failed", attempt=2),
    ])
    mock_transfer.create.side_effect = lambda batch: batch

    assert retry_failed_transfers() == 1
    (batch,) = mock_transfer.create.call_args[0]
    assert batch[0].external_id == "invoice-inv1-r3"


@patch("app.retry.starkbank.transfer")
def test_gives_up_after_max_attempts(mock_transfer):
    transfers = [make_transfer("inv1", "failed")] + [
        make_transfer("inv1", "failed", attempt=k) for k in range(2, 6)
    ]
    mock_transfer.query.return_value = iter(transfers)

    assert retry_failed_transfers() == 0
    mock_transfer.create.assert_not_called()


@patch("app.retry.starkbank.transfer")
def test_retries_each_eligible_invoice_once_per_sweep(mock_transfer):
    mock_transfer.query.return_value = iter([
        make_transfer("inv1", "failed", amount=100),
        make_transfer("inv2", "failed", amount=200),
    ])
    mock_transfer.create.side_effect = lambda batch: batch

    assert retry_failed_transfers() == 2
    assert mock_transfer.create.call_count == 2
