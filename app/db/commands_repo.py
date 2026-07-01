"""
Data access functions for the `commands_config` table.
"""
from app.db.supabase_client import supabase


def get_all_command_configs():
    result = supabase.table("commands_config").select("*").order("command_name").execute()
    return result.data


def get_recent_interactions(limit: int = 50):
    result = (
        supabase.table("interactions")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def upsert_command_config(command_name: str, enabled: bool, response_template: str):
    """
    Creates or updates a config row for a command. server_id is left null
    for now (single-server setup) — easy to extend later for multi-server.
    """
    existing = (
        supabase.table("commands_config")
        .select("*")
        .eq("command_name", command_name)
        .is_("server_id", "null")
        .execute()
    )
    if existing.data:
        supabase.table("commands_config").update(
            {"enabled": enabled, "response_template": response_template}
        ).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("commands_config").insert(
            {
                "command_name": command_name,
                "enabled": enabled,
                "response_template": response_template,
            }
        ).execute()