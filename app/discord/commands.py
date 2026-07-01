"""
Command handler logic. Each handler receives the parsed interaction data
and returns (response_text, action_taken_description).
"""


def handle_report(options: dict, user_display_name: str) -> tuple[str, str]:
    """
    Handles /report <text>.
    Simple rule: flag as 'urgent' if certain keywords are present.
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

    return response, action


def handle_status(options: dict, user_display_name: str) -> tuple[str, str]:
    """
    Handles /status. Just a simple health-check style reply.
    """
    response = "🟢 Bot is online and processing commands normally."
    action = "status_check"
    return response, action


# Registry mapping command name -> handler function
COMMAND_HANDLERS = {
    "report": handle_report,
    "status": handle_status,
}


def parse_options(interaction_data: dict) -> dict:
    """Converts Discord's options array format into a simple {name: value} dict."""
    options = interaction_data.get("options", [])
    return {opt["name"]: opt["value"] for opt in options}