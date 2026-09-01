import os

import pytest

from app.events import InMemoryEventStore, PostgresEventStore, create_event_store


class TestInMemoryEventStore:
    def test_first_time_event_is_processed(self):
        assert InMemoryEventStore().mark_processed("evt-1") is True

    def test_duplicate_event_is_rejected(self):
        store = InMemoryEventStore()
        store.mark_processed("evt-1")
        assert store.mark_processed("evt-1") is False

    def test_is_processed_reflects_marks(self):
        store = InMemoryEventStore()
        assert not store.is_processed("evt-1")
        store.mark_processed("evt-1")
        assert store.is_processed("evt-1")


def test_factory_returns_postgres_store_when_url_given():
    store = create_event_store("postgresql://user:pass@localhost:5/db")
    assert isinstance(store, PostgresEventStore)


def test_factory_falls_back_to_memory_without_url():
    assert isinstance(create_event_store(None), InMemoryEventStore)


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")
class TestPostgresEventStore:
    @pytest.fixture
    def store(self):
        store = PostgresEventStore(TEST_DATABASE_URL)
        yield store
        store._conn().execute("DELETE FROM processed_events")

    def test_mark_and_check(self, store):
        assert store.mark_processed("evt-pg-1") is True
        assert store.mark_processed("evt-pg-1") is False
        assert store.is_processed("evt-pg-1")
        assert not store.is_processed("evt-pg-2")

    def test_dedup_survives_new_connection(self, store):
        store.mark_processed("evt-pg-3")
        fresh = PostgresEventStore(TEST_DATABASE_URL)
        assert fresh.mark_processed("evt-pg-3") is False
