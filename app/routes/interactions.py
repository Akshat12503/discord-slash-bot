"""
The single endpoint Discord calls for every interaction (slash commands,
buttons, modals). Must:
  1. Verify the Ed25519 signature on every request.
  2. Answer PING (type 1) with PONG (type 1) immediately.
  3. Handle APPLICATION_COMMAND (type 2): defer immediately, then process
     in the background and edit the response — keeps us within Discord's
     ~3 second window regardless of how long downstream calls take.
"""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from app.discord.verify import verify_discord_signature
from app.discord.commands import COMMAND_HANDLERS, parse_options
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

    # Dedup: if we've already processed this exact interaction, do nothing further
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
            response_text = f"Unknown command: {command_name}"
            action = "unknown_command"
        else:
            response_text, action = handler(options, user_display_name)

        # Reply back to Discord (edit the deferred placeholder)
        reply_resp = await edit_original_response(interaction_token, response_text)
        replied_ok = reply_resp.status_code < 300

        # Mirror to second channel
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
        # Never let a downstream failure silently disappear — record it.
        update_interaction(
            interaction_id,
            status="failed",
            error_message=str(e),
        )


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
        # Dedup at the ACK stage too — if we've already seen this id, still
        # ack politely (Discord requires SOME response) but skip re-processing.
        interaction_id = payload["id"]
        existing = get_interaction_by_discord_id(interaction_id)
        if not (existing and existing.get("status") == "processed"):
            background_tasks.add_task(process_command, payload)
        return {"type": 5}  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

    return {"type": 1}