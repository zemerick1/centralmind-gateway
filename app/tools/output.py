"""
Output tools — post to Teams, Slack, generic webhooks, etc.
"""

import logging
from typing import Any, Dict, Optional

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


async def post_to_webhook(
    payload: Dict[str, Any],
    webhook_url: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generic POST to any webhook (Teams, custom, etc.).
    For Microsoft Teams, pass a nicely formatted Adaptive Card or simple text.
    """
    url = webhook_url or settings.output_webhook_url
    if not url:
        raise ValueError("No output_webhook_url configured")

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # Teams likes application/json with specific structure
            if "office.com" in url or "webhook.office.com" in url:
                # Simple text message for Teams (you can upgrade to Adaptive Cards later)
                body = {
                    "text": payload.get("text") or str(payload),
                    "title": title or "CentralMind Gateway Alert"
                }
            else:
                body = payload

            resp = await client.post(url, json=body)
            resp.raise_for_status()
            logger.info(f"Posted to webhook successfully (status {resp.status_code})")
            return {"status": "success", "status_code": resp.status_code}
        except Exception as e:
            logger.error(f"Failed to post to webhook: {e}")
            raise


async def post_to_slack(
    text: str,
    channel: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Post a simple message to Slack via Incoming Webhook."""
    url = webhook_url or settings.slack_webhook_url
    if not url:
        raise ValueError("No slack_webhook_url configured")

    payload = {"text": text}
    if channel:
        payload["channel"] = channel

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        logger.info("Posted to Slack successfully")
        return {"status": "success"}
