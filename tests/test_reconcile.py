from types import SimpleNamespace
from unittest.mock import call, patch

from app.events import InMemoryEventStore
from app.reconcile import reconcile


def make_event(id, log_type="credited"):
    invoice = SimpleNamespace(amount=1000, fee=0, id=f"inv-{id}")
    return SimpleNamespace(id=id, subscription="invoice",
                           log=SimpleNamespace(type=log_type, invoice=invoice))


@patch("app.reconcile.starkbank")
@patch("app.reconcile.handle_event", return_value="ok")
def test_reconcile_processes_and_marks_delivered(mock_handle, mock_sb):
    mock_sb.event.query.return_value = iter([make_event("e1"), make_event("e2", "created")])
    assert reconcile(InMemoryEventStore()) == 2
    mock_sb.event.query.assert_called_once_with(is_delivered=False)
    assert mock_sb.event.update.call_args_list == [
        call("e1", is_delivered=True),
        call("e2", is_delivered=True),
    ]


@patch("app.reconcile.starkbank")
@patch("app.reconcile.handle_event", side_effect=[RuntimeError("boom"), "ok"])
def test_reconcile_keeps_failed_event_undelivered(mock_handle, mock_sb):
    mock_sb.event.query.return_value = iter([make_event("e1"), make_event("e2")])
    assert reconcile(InMemoryEventStore()) == 1
    assert mock_sb.event.update.call_args_list == [call("e2", is_delivered=True)]
