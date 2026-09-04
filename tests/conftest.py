"""Test environment: fake credentials so app modules can be imported offline.

Values are ASSIGNED (not setdefault) before any app module is imported:
`load_dotenv()` does not override existing environment variables, so this is
what keeps a developer's real `.env` (real project id, real DATABASE_URL —
possibly the official 24h-run database) out of the test run.
"""
import os
import pathlib
import tempfile

import starkbank

_tmp = pathlib.Path(tempfile.mkdtemp(prefix="starkbank-tests-"))

_private_key, _ = starkbank.key.create()
_key_path = _tmp / "key.pem"
_key_path.write_text(_private_key)

os.environ["STARKBANK_ENVIRONMENT"] = "sandbox"
os.environ["STARKBANK_PROJECT_ID"] = "1234567890123456"
os.environ["STARKBANK_PRIVATE_KEY_PATH"] = str(_key_path)
# Unit tests always use the in-memory store; integration tests opt in
# explicitly via TEST_DATABASE_URL (never the real DATABASE_URL).
os.environ["DATABASE_URL"] = ""
os.environ["ISSUE_TOKEN"] = ""
os.environ["ISSUE_UNTIL"] = ""
