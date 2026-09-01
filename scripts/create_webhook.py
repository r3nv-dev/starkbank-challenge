"""Registers the webhook endpoint for invoice events.

Usage: python scripts/create_webhook.py https://your-public-url/webhook
"""
import sys

import starkbank

from app.config import setup_starkbank

if len(sys.argv) != 2:
    sys.exit(f"usage: python {sys.argv[0]} <public-webhook-url>")

setup_starkbank()
webhook = starkbank.webhook.create(url=sys.argv[1], subscriptions=["invoice"])
print(f"webhook created: id={webhook.id} url={webhook.url} subscriptions={webhook.subscriptions}")
