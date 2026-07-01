"""
Helpers for talking back to Discord's REST API:
  - editing the original deferred interaction response
  - posting a plain message to a channel (used for the mirror channel)
"""
import httpx
from app.config import DISCORD_APPLICATION_ID, DISCORD_BOT_TOKEN

DISCORD_API_BASE = "https://discord.com/api/v10"


async def edit_original_response(interaction_token: str, content: str):
    """
    Edits the original deferred response for an interaction.
    This is how we 'answer' after sending a type:5 (deferred) ack.
    """
    url = f"{DISCORD_API_BASE}/webhooks/{DISCORD_APPLICATION_ID}/{interaction_token}/messages/@original"
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(url, headers=headers, json={"content": content})
        return resp


async def post_to_webhook(webhook_url: str, content: str):
    """
    Posts a plain message to a Discord channel webhook (our mirror channel).
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(webhook_url, json={"content": content})
        return resp