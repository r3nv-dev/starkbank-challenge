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

## 4. Docs gap: the duplicated `external_id` error is undocumented

The API docs state that "Duplicated external_ids will cause failures", but the
error `code`/`message` returned in that case is not documented anywhere public.
Integrators who rely on `external_id` for idempotency (as this project does —
it is the hard guarantee against double payouts) have to guess which error
means "this transfer already exists, treat it as success" versus a genuine
failure that must propagate. Errors do arrive in a structured form
(`{"code": ..., "message": ...}`, e.g. `invalidProject` for a bad project id),
so documenting the specific code for duplicated `external_id`s would let
clients ack retries precisely instead of matching defensively on the message
text.
