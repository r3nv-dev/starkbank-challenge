from app.events import EventStore


def test_first_time_event_is_processed(tmp_path):
    store = EventStore(str(tmp_path / "events.db"))
    assert store.mark_processed("evt-1") is True


def test_duplicate_event_is_rejected(tmp_path):
    store = EventStore(str(tmp_path / "events.db"))
    assert store.mark_processed("evt-1") is True
    assert store.mark_processed("evt-1") is False


def test_dedup_survives_reopen(tmp_path):
    db = str(tmp_path / "events.db")
    EventStore(db).mark_processed("evt-1")
    assert EventStore(db).mark_processed("evt-1") is False
