"""Environment-based configuration and Stark Bank SDK setup."""
import os
from dataclasses import dataclass
from pathlib import Path

import starkbank
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    environment: str
    project_id: str
    private_key_path: str
    event_db_path: str


def load_settings() -> Settings:
    return Settings(
        environment=os.environ.get("STARKBANK_ENVIRONMENT", "sandbox"),
        project_id=os.environ["STARKBANK_PROJECT_ID"],
        private_key_path=os.environ.get("STARKBANK_PRIVATE_KEY_PATH", "private-key.pem"),
        event_db_path=os.environ.get("EVENT_DB_PATH", "data/events.db"),
    )


def setup_starkbank(settings: Settings | None = None) -> starkbank.Project:
    """Configure the global SDK user from environment settings."""
    settings = settings or load_settings()
    project = starkbank.Project(
        environment=settings.environment,
        id=settings.project_id,
        private_key=Path(settings.private_key_path).read_text(),
    )
    starkbank.user = project
    return project
