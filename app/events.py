"""Record of processed webhook events (idempotency).

Stark Bank redelivers events until it gets a 200, so the receiver must
tolerate duplicates. PostgreSQL keeps that record durable and shared across
instances; the in-memory store backs unit tests and credential-less local
runs. Losing this record is never a double-payment: the Transfer external_id
is the hard guarantee at the API level.
"""
import logging
from typing import Protocol

import psycopg

logger = logging.getLogger(__name__)


class EventStore(Protocol):
    def mark_processed(self, event_id: str) -> bool: ...

    def is_processed(self, event_id: str) -> bool: ...


class InMemoryEventStore:
    def __init__(self):
        self._seen: set[str] = set()

    def mark_processed(self, event_id: str) -> bool:
        if event_id in self._seen:
            return False
        self._seen.add(event_id)
        return True

    def is_processed(self, event_id: str) -> bool:
        return event_id in self._seen


class PostgresEventStore:
    """Connects lazily so the app can be imported without a database up."""

    def __init__(self, database_url: str):
        self._database_url = database_url
        self._connection: psycopg.Connection | None = None

    def _conn(self) -> psycopg.Connection:
        if self._connection is None or self._connection.closed:
            self._connection = psycopg.connect(self._database_url, autocommit=True)
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS processed_events (id TEXT PRIMARY KEY)"
            )
        return self._connection

    def mark_processed(self, event_id: str) -> bool:
        cursor = self._conn().execute(
            "INSERT INTO processed_events (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
            (event_id,),
        )
        return cursor.rowcount == 1

    def is_processed(self, event_id: str) -> bool:
        row = self._conn().execute(
            "SELECT 1 FROM processed_events WHERE id = %s", (event_id,)
        ).fetchone()
        return row is not None


def create_event_store(database_url: str | None) -> EventStore:
    if database_url:
        return PostgresEventStore(database_url)
    logger.warning("DATABASE_URL not set; using in-memory event store "
                   "(dedup is lost on restart; external_id still prevents double payouts)")
    return InMemoryEventStore()
