"""
Data access functions for the `interactions` table.
Centralizes all Supabase reads/writes related to logging interactions,
so route/handler code doesn't need to know about table structure directly.
"""
from app.db.supabase_client import supabase


def get_interaction_by_discord_id(discord_interaction_id: str):
    """Returns the existing row if this interaction was already recorded, else None."""
    result = (
        supabase.table("interactions")
        .select("*")
        .eq("discord_interaction_id", discord_interaction_id)
        .execute()
    )
    return result.data[0] if result.data else None


def create_interaction(
    discord_interaction_id: str,
    command_name: str,
    user_discord_id: str,
    user_display_name: str,
    raw_payload: dict,
):
    """Inserts a new interaction row immediately on receipt (status='received')."""
    result = (
        supabase.table("interactions")
        .insert(
            {
                "discord_interaction_id": discord_interaction_id,
                "command_name": command_name,
                "user_discord_id": user_discord_id,
                "user_display_name": user_display_name,
                "raw_payload": raw_payload,
                "status": "received",
            }
        )
        .execute()
    )
    return result.data[0] if result.data else None


def update_interaction(discord_interaction_id: str, **fields):
    """Updates fields on an existing interaction row (status, action_taken, replied, mirrored, error_message)."""
    supabase.table("interactions").update(fields).eq(
        "discord_interaction_id", discord_interaction_id
    ).execute()