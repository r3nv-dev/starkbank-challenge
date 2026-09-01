"""Test environment: fake credentials so app modules can be imported offline."""
import os
import pathlib
import tempfile

import starkbank

_tmp = pathlib.Path(tempfile.mkdtemp(prefix="starkbank-tests-"))

_private_key, _ = starkbank.key.create()
_key_path = _tmp / "key.pem"
_key_path.write_text(_private_key)

os.environ.setdefault("STARKBANK_PROJECT_ID", "1234567890123456")
os.environ.setdefault("STARKBANK_PRIVATE_KEY_PATH", str(_key_path))
# DATABASE_URL intentionally unset: app modules fall back to the in-memory store.
