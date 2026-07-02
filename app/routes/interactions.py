"""
The single endpoint Discord calls for every interaction (slash commands,
buttons, modals). Must:
  1. Verify the Ed25519 signature on every request.
  2. Answer PING (type 1) with PONG (type 1) immediately.
  3. Handle APPLICATION_COMMAND (type 2): defer, process in background.
  4. Handle MESSAGE_COMPONENT (type 3): button clicks — e.g. 'Mark Resolved'.
"""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from app.discord.verify import verify_discord_signature
from app.discord.commands import COMMAND_HANDLERS, parse_options, handle_resolve_button
from app.discord.api import edit_original_response, post_to_webhook
from app.db.interactions_repo import (
    get_interaction_by_discord_id,
    create_interaction,
    update_interaction,
)
from app.config import MIRROR_WEBHOOK_URL

router = APIRouter()


async def process_command(payload: dict):
    """
    Runs AFTER we've already responded to Discord with a deferred ack (type 5).
    Does the real work: dedup check, save, apply rule, edit response, mirror.
    """
    interaction_id = payload["id"]
    interaction_token = payload["token"]
    data = payload.get("data", {})
    command_name = data.get("name")
    member = payload.get("member", {})
    user = member.get("user", {}) or payload.get("user", {})
    user_discord_id = user.get("id")
    user_display_name = user.get("global_name") or user.get("username", "someone")

    existing = get_interaction_by_discord_id(interaction_id)
    if existing and existing.get("status") == "processed":
        return

    if not existing:
        create_interaction(
            discord_interaction_id=interaction_id,
            command_name=command_name,
            user_discord_id=user_discord_id,
            user_display_name=user_display_name,
            raw_payload=payload,
        )

    try:
        options = parse_options(data)
        handler = COMMAND_HANDLERS.get(command_name)

        if not handler:
            response_text, action, components = f"Unknown command: {command_name}", "unknown_command", []
        else:
            response_text, action, components = handler(options, user_display_name, interaction_id)

        reply_resp = await edit_original_response(interaction_token, response_text, components)
        replied_ok = reply_resp.status_code < 300

        mirrored_ok = False
        if MIRROR_WEBHOOK_URL:
            mirror_text = f"[{command_name}] {user_display_name}: {response_text}"
            mirror_resp = await post_to_webhook(MIRROR_WEBHOOK_URL, mirror_text)
            mirrored_ok = mirror_resp.status_code < 300

        update_interaction(
            interaction_id,
            status="processed",
            action_taken=action,
            replied=replied_ok,
            mirrored=mirrored_ok,
        )

    except Exception as e:
        update_interaction(
            interaction_id,
            status="failed",
            error_message=str(e),
        )


async def process_button_click(payload: dict):
    """
    Runs after a button interaction is ack'd. Logs the click as its own
    interaction row (separate from the original /report), then updates
    the resolved status on the original report row if we can find it.
    """
    interaction_id = payload["id"]
    data = payload.get("data", {})
    custom_id = data.get("custom_id", "")
    member = payload.get("member", {})
    user = member.get("user", {}) or payload.get("user", {})
    user_discord_id = user.get("id")
    user_display_name = user.get("global_name") or user.get("username", "someone")

    existing = get_interaction_by_discord_id(interaction_id)
    if not existing:
        create_interaction(
            discord_interaction_id=interaction_id,
            command_name=f"button:{custom_id.split(':')[0]}",
            user_discord_id=user_discord_id,
            user_display_name=user_display_name,
            raw_payload=payload,
        )

    try:
        # Mark the ORIGINAL report interaction as resolved, if we can find it
        original_id = custom_id.split(":", 1)[1] if ":" in custom_id else None
        if original_id:
            update_interaction(original_id, action_taken="resolved_by_button")

        update_interaction(interaction_id, status="processed", action_taken="button_click_processed")
    except Exception as e:
        update_interaction(interaction_id, status="failed", error_message=str(e))


@router.post("/interactions")
async def interactions(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")

    if not verify_discord_signature(signature, timestamp, body):
        raise HTTPException(status_code=401, detail="Invalid request signature")

    payload = await request.json()
    interaction_type = payload.get("type")

    if interaction_type == 1:
        return {"type": 1}  # PONG

    if interaction_type == 2:
        interaction_id = payload["id"]
        existing = get_interaction_by_discord_id(interaction_id)
        if not (existing and existing.get("status") == "processed"):
            background_tasks.add_task(process_command, payload)
        return {"type": 5}  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

    if interaction_type == 3:
        # Button click — respond immediately with UPDATE_MESSAGE (type 7),
        # directly editing the message the button lives on, synchronously.
        data = payload.get("data", {})
        custom_id = data.get("custom_id", "")

        if custom_id.startswith("resolve:"):
            new_content, new_components, original_id = handle_resolve_button(custom_id)
            background_tasks.add_task(process_button_click, payload)
            return {
                "type": 7,  # UPDATE_MESSAGE
                "data": {"content": new_content, "components": new_components},
            }

        # Unknown component — ack with no-op update
        return {"type": 7, "data": {}}

    return {"type": 1}