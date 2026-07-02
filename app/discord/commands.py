"""
Command handler logic. Each handler receives the parsed interaction data
and returns (response_text, action_taken_description, components, ai_summary).
"""
from app.ai.gemini import summarize_report


async def handle_report(options: dict, user_display_name: str, discord_interaction_id: str = None) -> tuple[str, str, list, str | None]:
    """
    Handles /report <text>.
    Simple rule: flag as 'urgent' if certain keywords are present.
    Also runs the report text through Gemini for a short category/summary tag.
    Returns (response_text, action_taken, components, ai_summary).
    """
    text = options.get("text", "")
    urgent_keywords = ["urgent", "asap", "broken", "down", "critical"]
    is_urgent = any(word in text.lower() for word in urgent_keywords)

    if is_urgent:
        response = f"🚨 Urgent report received from {user_display_name}: \"{text}\""
        action = "flagged_urgent"
    else:
        response = f"✅ Report received from {user_display_name}: \"{text}\""
        action = "logged_normal"

    ai_summary = await summarize_report(text)
    if ai_summary:
        response += f"\n🏷️ AI triage: {ai_summary}"

    components = [
        {
            "type": 1,  # ACTION_ROW
            "components": [
                {
                    "type": 2,  # BUTTON
                    "style": 3,  # SUCCESS (green)
                    "label": "Mark Resolved",
                    "custom_id": f"resolve:{discord_interaction_id}",
                }
            ],
        }
    ]

    return response, action, components, ai_summary


async def handle_status(options: dict, user_display_name: str, discord_interaction_id: str = None) -> tuple[str, str, list, str | None]:
    """
    Handles /status. Just a simple health-check style reply. No buttons, no AI.
    """
    response = "🟢 Bot is online and processing commands normally."
    action = "status_check"
    return response, action, [], None


# Registry mapping command name -> handler function
COMMAND_HANDLERS = {
    "report": handle_report,
    "status": handle_status,
}


def parse_options(interaction_data: dict) -> dict:
    """Converts Discord's options array format into a simple {name: value} dict."""
    options = interaction_data.get("options", [])
    return {opt["name"]: opt["value"] for opt in options}


def handle_resolve_button(custom_id: str) -> tuple[str, list, str | None]:
    """
    Handles a 'Mark Resolved' button click.
    Returns (new_content, new_components, original_interaction_id) to
    directly update the message and locate the original report row.
    """
    original_interaction_id = custom_id.split(":", 1)[1] if ":" in custom_id else None
    new_content = "✅ This report has been marked as resolved."
    new_components = []  # remove the button
    return new_content, new_components, original_interaction_id