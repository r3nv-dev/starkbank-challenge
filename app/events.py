"""SQLite-backed record of processed webhook events (idempotency).

Stark Bank redelivers events until it gets a 200, so the receiver must
tolerate duplicates. Persisting processed ids keeps restarts safe too.
"""
import sqlite3
from pathlib import Path


class EventStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS processed_events (id TEXT PRIMARY KEY)"
        )
        self._conn.commit()

    def mark_processed(self, event_id: str) -> bool:
        """Return True if this event was not seen before (and mark it)."""
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO processed_events (id) VALUES (?)", (event_id,)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def is_processed(self, event_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM processed_events WHERE id = ?", (event_id,)
        ).fetchone()
        return row is not None
