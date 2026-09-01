"""Webhook receiver: verifies event signatures and reacts to credited invoices."""
import logging

import starkbank
from fastapi import FastAPI, HTTPException, Request

from app.config import load_settings, setup_starkbank
from app.events import EventStore
from app.handlers import handle_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = load_settings()
setup_starkbank(settings)
store = EventStore(settings.event_db_path)

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
