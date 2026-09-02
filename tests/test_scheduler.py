"""Tests for the 24h scheduler loop (8 cycles, 3h apart by default)."""
from unittest.mock import call, patch

from app.scheduler import run


@patch("app.scheduler.time.sleep")
@patch("app.scheduler.issue_random_invoices")
@patch("app.scheduler.setup_starkbank")
def test_runs_all_cycles_sleeping_between_them(mock_setup, mock_issue, mock_sleep):
    run(cycles=8, interval_hours=3)
    mock_setup.assert_called_once()
    assert mock_issue.call_count == 8
    # 7 sleeps: between cycles only, none after the last one
    assert mock_sleep.call_args_list == [call(3 * 3600)] * 7


@patch("app.scheduler.time.sleep")
@patch("app.scheduler.issue_random_invoices",
       side_effect=[RuntimeError("api down"), None, None])
@patch("app.scheduler.setup_starkbank")
def test_failed_cycle_does_not_abort_the_run(mock_setup, mock_issue, mock_sleep):
    run(cycles=3, interval_hours=1)
    assert mock_issue.call_count == 3
