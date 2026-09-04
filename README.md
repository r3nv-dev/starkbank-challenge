# Stark Bank Challenge

Backend integration for the Stark Bank developer challenge:

1. **Issues 8–12 invoices every 3 hours for 24 hours** to randomly generated
   people (names + CPFs with valid check digits) in the sandbox environment.
2. **Receives invoice webhook events**, verifies their ECDSA signature against
   the raw request body, and on each `credited` invoice log **transfers the
   received amount minus fees** to the Stark Bank S.A. account
   (bank code 20018183, branch 0001, account 6341320293482496).

Bonus: [findings on Stark Bank's public code & docs](docs/starkbank-findings.md).

## Architecture

```
 every 3h (scheduler CLI or any cron)        Stark Bank API (sandbox)
┌──────────────────────┐  POST /issue  ┌──────────────────────────────┐
│  external scheduler  │──────────────▶│  invoice.create (batch 8-12) │
└──────────────────────┘  X-Issue-Token└──────────────┬───────────────┘
                                                      │ invoice.credited
                                                      ▼ (signed webhook)
┌─────────────────────────────────────────────────────────────────────┐
│  app/webhook_app.py (FastAPI)                                       │
│  POST /webhook: verify Digital-Signature over the RAW body          │
│    └─▶ app/handlers.handle_event                                    │
│          ├─ only invoice + credited  ─▶ transfer(amount - fee)      │
│          ├─ dedup via PostgreSQL processed_events                   │
│          └─ mark processed only AFTER the transfer succeeds         │
└─────────────────────────────────────────────────────────────────────┘
             ▲
             │ reuses the same handler
┌────────────┴────────────┐   ┌────────────────────────────────────────┐
│  app/reconcile.py       │   │  app/retry.py                          │
│  event.query(            │   │  recreates transfers that failed       │
│    is_delivered=False)   │   │  asynchronously, with double-pay guards│
│  catches lost webhooks   │   │  (python -m app.retry)                 │
└─────────────────────────┘   └────────────────────────────────────────┘
```

- `app/webhook_app.py` — HTTP edge: `POST /webhook` (signature-authenticated),
  `POST /issue` (token-authenticated, 24h-window guarded), `GET /health`.
- `app/handlers.py` — the one business handler, shared by the webhook and the
  reconciliation job.
- `app/transfers.py` — builds the Transfer with `external_id=invoice-<id>`.
- `app/events.py` — processed-event store: PostgreSQL, with an in-memory
  fallback when `DATABASE_URL` is unset (tests / credential-less runs).
- `app/invoices.py`, `app/people.py` — invoice batches for random people with
  CPF check digits computed correctly.
- `app/scheduler.py` — CLI loop for the 24h run (8 cycles, 3h apart) when not
  using an external cron.
- `app/reconcile.py` — undelivered-event sweep (see design decisions).
- `app/retry.py` — recreates asynchronously-failed transfers, guarded against
  double payouts (see design decisions).

## Design decisions

| Decision | Why |
|---|---|
| Only `credited` invoice logs trigger a transfer | `paid` precedes the actual credit of the money in the account; reacting to both would pay the same invoice twice. |
| Event marked processed only **after** the transfer succeeds | A transfer failure leaves the event unmarked → the endpoint returns 500 → Stark redelivers and the event is retried. Marking first would silently drop the payout. |
| Transfer `external_id = invoice-<id>` | Stark rejects a reused external_id, so even if the local store is lost or two instances race, a double payout is impossible. The store is the primary guard; the external_id is the backstop. In the sandbox this rejection is **asynchronous** (create returns 200, the transfer later fails as "Duplicated transfer" — see [findings #4](docs/starkbank-findings.md)); it still blocks the second payout. |
| Retry job (`python -m app.retry`) | Because a transfer can be accepted and then fail asynchronously ("Duplicated transfer", "Target account is blocked" — both observed on the challenge's own destination account), the event is already marked processed by the time it fails. This sweep recreates failed transfers with a fresh `invoice-<id>-r<n>` external_id, but only when the invoice has no live/successful transfer — so it never double-pays. |
| Reconciliation job (`python -m app.reconcile`) | Stark retries webhook delivery only 3 times (5min/30min/120min) and then gives up. The official docs recommend sweeping `event.query(is_delivered=False)` periodically; the job reuses the exact same handler as the webhook. |
| Signature verified over the **raw** request body | `starkbank.event.parse` must see the bytes Stark signed; re-serialized JSON breaks verification. Invalid signatures → 400, nothing processed. |
| `/issue` compares tokens with `secrets.compare_digest` | Constant-time comparison; and an `ISSUE_UNTIL` guard closes the 24h issuing window server-side even if the external scheduler keeps firing. |
| No payer PII in logs | Invoice logs carry id/amount only — never the person's name or CPF. |
| PostgreSQL for dedup, lean stack otherwise | Durable, restart-safe idempotency record shared across instances; no heavy framework — FastAPI + the official SDK + psycopg only. |

## Setup

Requires Python 3.11+, Docker (for PostgreSQL) and a Stark Bank **sandbox** account.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

1. Generate the ECDSA key pair: `python scripts/generate_keys.py`
2. In the sandbox web dashboard, create a **Project** using the printed public key.
3. Copy `.env.example` to `.env`; fill in `STARKBANK_PROJECT_ID` and set
   `ISSUE_TOKEN` (`openssl rand -hex 32`).
4. Start the dedup database: `docker compose up -d db`
5. Expose the webhook publicly (e.g. `ngrok http 8000`) and register it —
   the account must have exactly one active webhook:
   `python scripts/create_webhook.py https://<public-url>/webhook`

## Running

```bash
# webhook receiver + issue endpoint
uvicorn app.webhook_app:app --port 8000

# the 24h run, option A — self-contained CLI (8 cycles x 3h):
python -m app.scheduler

# the 24h run, option B — any external cron hitting the endpoint:
curl -X POST -H "X-Issue-Token: $ISSUE_TOKEN" localhost:8000/issue

# reconciliation sweep (run periodically / after downtime):
python -m app.reconcile

# retry transfers that failed asynchronously (run periodically):
python -m app.retry
```

Or containerized:

```bash
docker build -t starkbank-challenge .
docker run --rm -p 8080:8080 --env-file .env \
  -v "$PWD/private-key.pem:/app/private-key.pem:ro" starkbank-challenge
```

The service is a stateless container (state lives in PostgreSQL and in the
Transfer external_ids), so it deploys unchanged to Cloud Run or any container
platform, with the platform's scheduler hitting `/issue` every 3 hours.

## Tests

```bash
pytest                    # unit + HTTP-layer tests, no credentials needed
docker compose up -d db   # then, to also run the PostgreSQL integration tests:
TEST_DATABASE_URL=postgresql://stark:stark@localhost:5432/starkbank pytest
```

All Stark Bank API calls are mocked in tests. Covered behaviors include:
signature rejection, `credited`-only processing, duplicate-event dedup,
failed-transfer redelivery semantics, duplicated-external_id ack, fee-exceeds-
amount edge, issue-token auth, 24h-window guard, reconciliation sweep, and
PII-free logging.

## Evidence — sandbox run

Captured from a live run against the Stark Bank sandbox (real ids; no PII, no
credentials). The full event-driven loop is exercised end to end:

- Over the 24h run the service **issued invoices in batches of 8–12 every 3
  hours** to random people; the sandbox auto-paid a large share of them, and
  every payment produced an `invoice.credited` webhook. A representative
  snapshot mid-run: **31 issued, 17 paid, 17 `credited` events processed**.
- Every credited webhook was delivered to `POST /webhook`, its **ECDSA
  signature verified against the raw body**, and handled — invalid signatures
  are rejected with 400, `created`/`paid` logs ignored, only `credited` acted
  on (`event.query(is_delivered=False)` returns 0 → all webhooks delivered).
- For each credited invoice the service created a **Transfer of `amount − fee`
  to the exact challenge account** (bank `20018183`, branch `0001`, account
  `6341320293482496`, Stark Bank S.A., payment). Example:
  invoice `5514060439224320` (credited `amount=5016`, `fee=0`) → Transfer to
  `20018183 / 6341320293482496`.

**Environment note (not a code issue):** every Transfer to the mandated
destination account settled `failed` with `errors: ["Target account is
blocked"]` and was refunded (balance returns intact), and some first attempts
surfaced a misleading `["Duplicated transfer"]` on unique external_ids. In
other words the sandbox's destination account was blocked during the run, so no
payout could complete regardless of the client. This is documented as a finding
(see [docs/starkbank-findings.md](docs/starkbank-findings.md) #4 and #5); the
`app/retry.py` sweep keeps re-attempting (bounded, with double-payout guards),
so payouts converge automatically once the account is unblocked.
