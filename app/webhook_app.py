"""HTTP edge: webhook receiver and the scheduler-facing issue endpoint."""
import logging
import secrets
from datetime import datetime, timezone

import starkbank
from fastapi import FastAPI, Header, HTTPException, Request

from app.config import load_settings, setup_starkbank
from app.events import create_event_store
from app.handlers import handle_event
from app.invoices import issue_random_invoices

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = load_settings()
setup_starkbank(settings)
store = create_event_store(settings.database_url)

app = FastAPI(title="starkbank-challenge webhook")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    content = (await request.body()).decode("utf-8")
    signature = request.headers.get("Digital-Signature", "")

    try:
        event = starkbank.event.parse(content=content, signature=signature)
    except starkbank.error.InvalidSignatureError:
        logger.warning("rejected event with invalid signature")
        raise HTTPException(status_code=400, detail="invalid signature")

    return {"status": handle_event(event, store)}


@app.post("/issue")
def issue(x_issue_token: str = Header(default="")):
    """Called by an external scheduler every 3h; issues one batch of 8-12 invoices."""
    if not settings.issue_token:
        raise HTTPException(status_code=503, detail="issuing disabled: ISSUE_TOKEN not set")
    if not secrets.compare_digest(x_issue_token, settings.issue_token):
        raise HTTPException(status_code=403, detail="forbidden")
    if settings.issue_until:
        until = datetime.fromisoformat(settings.issue_until)
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > until:
            logger.info("issue window closed at %s; skipping", settings.issue_until)
            return {"status": "window-closed", "issued": 0}
    invoices = issue_random_invoices()
    return {"status": "ok", "issued": len(invoices)}
