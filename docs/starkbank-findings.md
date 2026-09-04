# Findings on Stark Bank public code & docs

Reported in the spirit of the challenge's bonus ("find issues on our public
code or API"). All items were re-verified on **2026-09-01** against the
versions listed below — nothing here is copied from old reports without
checking the current state.

Verified versions: `starkbank` 2.35.0 · `starkcore` 0.7.0 · `starkbank-ecdsa` 2.3.1.

## 1. Historical: universal signature forgery in starkbank-ecdsa (CVE-2021-43572)

Versions of `starkbank-ecdsa` before **2.0.1** accepted `(r=0, s=0)` as a valid
signature for *any* message and *any* public key, because `verify()` did not
range-check the signature components — an attacker could forge webhook events
without knowing any private key. This was part of a family of advisories
against the Stark Bank ECDSA libraries (Python/Node/.NET/Elixir/Java), tracked
as GHSA-9wx7-jrvc-28mm / CVE-2021-43572 for the Python package.

- Verified today via OSV: the advisory lists `starkbank-ecdsa` fixed in
  **2.0.1**; the dependency chain currently installed by `starkbank` 2.35.0
  resolves to **2.3.1**, so current installs are safe.
- Also verified in the installed 2.3.1 source: signing now derives the nonce
  deterministically per **RFC 6979** (`ellipticcurve/ecdsa.py` uses
  `RandomInteger.rfc6979`), which removes the nonce-reuse failure mode;
  the 2.3.0 changelog entry (2026-04-23) records this as "Security changes".

Lesson applied in this project: the webhook endpoint never processes a payload
before `starkbank.event.parse` verifies the `Digital-Signature` header against
the **raw** request body; invalid signatures are rejected with HTTP 400.

## 2. Open: sdk-python installation fails on non-UTF-8 environments (issue #108)

[Issue #108](https://github.com/starkbank/sdk-python/issues/108) ("Can't
install the package due to parsing error") is still **open** (verified
2026-09-01; last activity 2023-08-28, no maintainer response). The reporter's
environment fails to decode the `”` (U+201D) character while installing from
source.

Root cause, confirmed in the current `starkbank-2.35.0` sdist:

```python
# setup.py
try:
    with open('README.md', encoding="utf-8") as f:
        README = f.read()
except:                       # bare except
    with open('README.md') as f:   # falls back to the locale's encoding
        README = f.read()
```

`README.md` still contains a U+201D character, so on any environment where the
fallback path runs, the locale-dependent `open()` raises a `UnicodeDecodeError`
and the install aborts. Suggested fix: drop the bare `except:` and always read
with `encoding="utf-8"` (the SDK no longer needs a Python 2 fallback), or move
the metadata to `pyproject.toml` where the build backend handles encoding.

## 3. Docs: Invoice docstrings mention a Boleto-only status

`starkbank/invoice/__invoice.py` (v2.35.0, lines 41, 140 and 168) documents
the Invoice `status` as:

```
- status [string]: current Invoice status. ex: "registered" or "paid"
```

`"registered"` is not an Invoice status — Invoices go through
`created / paid / canceled / overdue / expired` (the credit itself appears as
a `credited` **log**, not a status). `"registered"` belongs to Boleto, so this
looks like a copy-paste leftover that can mislead integrators writing status
filters (e.g. `invoice.query(status="registered")` never matches anything).

## 4. API behavior: a duplicated `external_id` is NOT rejected at create time — it fails asynchronously

This is the most important finding, and it contradicts the documentation. The
docs say "Duplicated external_ids will cause failures", which every integrator
reads as *synchronous rejection* — i.e. `transfer.create` raises so you can
catch it and treat the retry as idempotent.

Observed in the sandbox on 2026-09-04 (real transfer ids):
`transfer.create([Transfer(external_id="invoice-5725166671757312", ...)])` for
an `external_id` **already used** returned normally with HTTP 200 and a
Transfer in status `created` (id `6514870478438400`) — **no exception**.
Seconds later a `transfer.log` of type `failed` appeared carrying
`errors: ["Duplicated transfer"]`, and the transfer settled as `failed`.

Consequences for integrators:

- The natural idempotency pattern — `try: transfer.create(...) except: # already
  paid` — is dead code. There is no exception; the create looks successful.
- To tell "already paid, safe to ack" from "must retry", you must poll
  `transfer.log` for an async `failed` and then **string-match the English
  prose** `"Duplicated transfer"` — there is no error `code`, no reference to
  the original transfer, no `external_id` echoed back. The error is a bare
  string in a list.
- (`transfer.create` on genuinely bad input *does* raise synchronously with a
  structured `{"code","message"}` — e.g. `invalidProject`. So the API is
  inconsistent: some failures are synchronous+structured, the duplicate one is
  asynchronous+free-text.)

## 5. Sandbox: first-ever transfers to the challenge's own destination account failed as "Duplicated transfer"

During the official run, the first (and only) transfer created for each of 9
credited invoices — each with a unique `external_id`, to the challenge's
mandated destination account (bank `20018183`, account `6341320293482496`) —
**all** settled `failed` with `errors: ["Duplicated transfer"]`. Verified there
was nothing to duplicate: `invoice.log.query(types=["credited"])` returned
exactly 9 logs for 9 distinct invoices, and our handler issued exactly one
transfer per invoice. So the message is simply wrong — nothing was duplicated.

Recreating the same payout with a fresh `external_id` then surfaced a *different*
async error on the same destination: `errors: ["Target account is blocked"]`,
followed by a `refunded` log. In other words, the exact account every candidate
is instructed to transfer to was, during the challenge window, async-rejecting
first-time transfers behind a misleading error string — a failure entirely
outside the integrator's code that only a reconcile/retry job survives.

## 6. Code: `event.parse` verifies the signature over a re-serialized JSON fallback (parsing differential)

In `starkcore/utils/parse.py`, `_is_signature_valid` first verifies the ECDSA
signature against the **raw** body (correct). If that fails, it falls back to
`Ecdsa.verify(dumps(loads(content), sort_keys=True), ...)` — i.e. it re-parses
and re-serializes the JSON and accepts a signature valid over *that* normalized
form. This means the signature does not authenticate the exact received bytes:
a signature computed over a key-reordered / re-whitespaced encoding of the same
JSON also passes. Since `parse_and_verify` then builds the event object with
`loads(content, strict=False)` — which tolerates control characters and, per
`json`, silently collapses duplicate keys (last value wins) — the bytes that
were authenticated and the object the application acts on can diverge. Any
integrator who assumes "the signature covers exactly these bytes" (e.g. hashing
the raw body as an idempotency key) is mistaken.

## 7. Code: webhook trust reduces to an unpinned TLS fetch cached in a process-global dict

`_get_public_key` fetches Stark's signing key from `GET /public-key` and stores
it in `cache = {}` (`starkcore/utils/cache.py`) — a plain module-global dict,
no TTL, no signature over the cached key. The network layer (`request.py`)
calls `requests` without `verify=`/certificate pinning, so it trusts any of the
system's ~100 root CAs. The whole webhook trust chain therefore rests on that
one unauthenticated fetch: whoever can answer for `sandbox.api.starkbank.com`
during it (DNS cache poisoning, or a mis-issued/compromised CA cert) injects
their own public key into the cache, after which forged webhook events signed
with the attacker's key verify as genuine. The `refresh=True` retry path
re-fetches on any verification failure, giving a second injection window on
demand. Pinning the key (it ships in every SDK release anyway) would remove the
network dependency from the trust decision entirely.

## 8. Code: ECDSA `verify` accepts high-S signatures (malleability)

`ellipticcurve/ecdsa.py` `verify` range-checks `1 <= s <= N-1` but does not
enforce low-S (`s <= N/2`), while `sign` always produces low-S. So for any valid
signature `(r, s)` the twin `(r, N-s)` also verifies, and `Signature.fromDer`'s
canonical-DER check does not catch it (both are canonical). Harmless for a
webhook that only asks "is this signed by Stark?", but a real bypass for any
integrator who uses the signature bytes themselves as a dedup/idempotency key,
since one authentic event then has two distinct valid signatures.
