import os
"""
One-off script to register (or update) slash commands with Discord.
Run this whenever you add/change a command definition.
Usage: python scripts/register_commands.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from app.config import DISCORD_APPLICATION_ID, DISCORD_BOT_TOKEN

COMMANDS = [
    {
        "name": "report",
        "description": "Submit a report",
        "type": 1,  # CHAT_INPUT (slash command)
        "options": [
            {
                "name": "text",
                "description": "What are you reporting?",
                "type": 3,  # STRING
                "required": True
            }
        ]
    },
    {
        "name": "status",
        "description": "Check the bot's status",
        "type": 1
    }
]

def main():
    DISCORD_TEST_GUILD_ID = os.getenv("DISCORD_TEST_GUILD_ID")
    url = f"https://discord.com/api/v10/applications/{DISCORD_APPLICATION_ID}/guilds/{DISCORD_TEST_GUILD_ID}/commands"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    for cmd in COMMANDS:
        resp = httpx.post(url, headers=headers, json=cmd)
        if resp.status_code in (200, 201):
            print(f"✅ Registered /{cmd['name']}")
        else:
            print(f"❌ Failed to register /{cmd['name']}: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    main()