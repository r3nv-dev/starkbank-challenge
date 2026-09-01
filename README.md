# Stark Bank Challenge

Backend integration for the Stark Bank developer challenge:

1. **Issues 8–12 invoices every 3 hours for 24 hours** to randomly generated people (valid CPF check digits) in the sandbox environment.
2. **Receives invoice webhook events**, verifies their ECDSA signature, and on each `credited` invoice **sends the received amount minus fees** to the Stark Bank S.A. account via a Transfer.

## Architecture

```
┌────────────────┐   every 3h    ┌─────────────────┐
│ app/scheduler  │──────────────▶│  Stark Bank API │
│ (invoice batch)│               │    (sandbox)    │
└────────────────┘               └────────┬────────┘
                                          │ invoice.credited event
                                          ▼
                                 ┌─────────────────┐    Transfer (amount - fee)
                                 │ app/webhook_app │───────────────────────────▶
                                 │    (FastAPI)    │      Stark Bank S.A.
                                 └─────────────────┘
```

- `app/scheduler.py` — CLI loop: 8 cycles, 3h apart (configurable), each issuing 8–12 random invoices.
- `app/webhook_app.py` — FastAPI receiver at `POST /webhook`. Rejects payloads with invalid `Digital-Signature` (verified by the SDK against Stark Bank's public key).
- `app/transfers.py` — builds the Transfer with `external_id=invoice-<id>`, so the API itself refuses duplicates.
- `app/events.py` — SQLite record of processed event ids: webhook redeliveries are acknowledged but not reprocessed.

## Setup

Requires Python 3.11+ and a Stark Bank **sandbox** account.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

1. Generate the ECDSA key pair: `python scripts/generate_keys.py`
2. In the sandbox web dashboard, create a **Project** using the printed public key.
3. Copy `.env.example` to `.env` and fill in `STARKBANK_PROJECT_ID`.
4. Expose the webhook publicly (e.g. `ngrok http 8000`) and register it:
   `python scripts/create_webhook.py https://<public-url>/webhook`

## Running

```bash
# webhook receiver
uvicorn app.webhook_app:app --port 8000

# invoice scheduler (8 cycles x 3h = 24h)
python -m app.scheduler
```

## Tests

```bash
pytest
```

All Stark Bank API calls are mocked in tests; no credentials needed.

## Design notes

- **Signature verification**: every webhook payload is verified with `starkbank.event.parse` before any processing — unauthenticated requests get a 400.
- **Idempotency in two layers**: locally via the processed-events store, and at the API via the Transfer `external_id`. A redelivered event can never cause a double payout.
- **Fee handling**: the transferred amount is `invoice.amount - invoice.fee`; if fees consume the whole amount, no transfer is made.
- **Failure isolation**: a failed scheduler cycle logs the error and waits for the next cycle instead of aborting the 24h run.
