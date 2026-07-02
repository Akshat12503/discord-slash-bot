# Discord Slash-Command Bot

A web app + Discord bot that handles slash commands via Discord's HTTP Interactions API, logs every command to a database, replies in Discord, mirrors notifications to a second channel, and exposes an admin dashboard to view the live log and configure command behavior.

## What it does

- `/status` — health-check style command, bot replies confirming it's online.
- `/report <text>` — submits a report; a simple keyword rule flags it as "urgent" if it contains words like `urgent`, `asap`, `broken`, `down`, `critical`.
- Every command is:
  1. Verified via Discord's Ed25519 request signature (rejects forged/unsigned requests).
  2. Deduplicated on Discord's `interaction_id` (safe against retried deliveries).
  3. Acknowledged within Discord's ~3 second window via a deferred response, then processed in the background.
  4. Logged to a Postgres database (Supabase) with status tracking (`received` → `processed`/`failed`).
  5. Replied to in Discord (editing the deferred response).
  6. Mirrored to a second Discord channel via webhook.
- An admin dashboard (behind login) shows a live command log and lets the admin toggle commands on/off and set a custom response template per command.

## Tech stack

- **Backend**: Python, FastAPI
- **Database + Auth**: Supabase (Postgres + Auth)
- **Frontend**: Server-rendered HTML (Jinja2 templates), light JS polling for live log updates
- **Notifications mirror**: Discord channel webhook
- **Hosting**: [FILL IN AFTER DEPLOY — e.g. Render]

## Project structure

app/
├── main.py                  # FastAPI app entrypoint
├── config.py                 # loads environment variables
├── auth/
│   ├── session.py             # signed-cookie session handling
│   ├── supabase_auth.py       # Supabase Auth login verification
│   └── dependency.py          # route protection helper
├── discord/
│   ├── verify.py               # Ed25519 signature verification
│   ├── commands.py             # slash command business logic
│   └── api.py                  # Discord REST API helpers (reply, mirror)
├── db/
│   ├── supabase_client.py      # Supabase client (service role)
│   ├── interactions_repo.py    # interactions table access
│   └── commands_repo.py        # commands_config table access
└── routes/
├── interactions.py         # POST /interactions — Discord's endpoint
├── auth_routes.py          # /login, /logout
└── dashboard.py             # /dashboard, /dashboard/data, /dashboard/config
templates/                      # Jinja2 HTML templates
scripts/
└── register_commands.py        # one-off script to register slash commands with Discord

## Running locally

### Prerequisites
- Python 3.11+
- A Discord account + server you can add a bot to
- A free Supabase account
- [ngrok](https://ngrok.com) (or similar) for local testing, since Discord requires a public HTTPS URL

### Setup

1. Clone the repo and create a virtual environment:
git clone https://github.com/Akshat12503/discord-slash-bot.git
cd discord-slash-bot
python -m venv venv
venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt

2. Copy `.env.example` to `.env` and fill in real values (see **Environment variables** below).

3. Create the database tables — run the SQL in `supabase_schema.sql` (or see below) in your Supabase project's SQL Editor.

4. Register slash commands with Discord:
python scripts/register_commands.py

5. Run the app:
uvicorn app.main:app --port 8000

6. In a separate terminal, expose it publicly for Discord to reach:
ngrok http 8000

7. In the [Discord Developer Portal](https://discord.com/developers/applications), set your application's **Interactions Endpoint URL** to `https://<your-ngrok-url>/interactions`.

8. Invite the bot to your server using the OAuth2 URL Generator (scopes: `bot`, `applications.commands`).

9. Visit `https://<your-ngrok-url>/login` to access the dashboard.

### Environment variables

See `.env.example` for the full list. Summary:

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side Supabase key (full access, keep secret) |
| `SUPABASE_ANON_KEY` | Public Supabase key, used for auth login calls |
| `DISCORD_APPLICATION_ID` | Discord application ID |
| `DISCORD_PUBLIC_KEY` | Used to verify Discord's request signatures |
| `DISCORD_BOT_TOKEN` | Used to register slash commands |
| `DISCORD_TEST_GUILD_ID` | Your test server's ID, for guild-scoped (instant) command registration |
| `MIRROR_WEBHOOK_URL` | Discord webhook URL for the second/mirror channel |
| `SESSION_SECRET` | Random secret used to sign dashboard login session cookies |

### Database schema

```sql
create table servers (
    id uuid primary key default gen_random_uuid(),
    discord_guild_id text unique not null,
    guild_name text,
    notify_channel_id text,
    mirror_type text default 'slack',
    mirror_webhook_url text,
    created_at timestamptz default now()
);

create table commands_config (
    id uuid primary key default gen_random_uuid(),
    server_id uuid references servers(id) on delete cascade,
    command_name text not null,
    enabled boolean default true,
    response_template text,
    rule_config jsonb default '{}',
    created_at timestamptz default now(),
    unique(server_id, command_name)
);

create table interactions (
    id uuid primary key default gen_random_uuid(),
    discord_interaction_id text unique not null,
    server_id uuid references servers(id) on delete set null,
    command_name text,
    user_discord_id text,
    user_display_name text,
    raw_payload jsonb,
    action_taken text,
    replied boolean default false,
    mirrored boolean default false,
    status text default 'received',
    error_message text,
    created_at timestamptz default now()
);

create index idx_interactions_created_at on interactions(created_at desc);

alter table servers enable row level security;
alter table commands_config enable row level security;
alter table interactions enable row level security;
```

Row Level Security is enabled with no policies — only the backend, using the service_role key (which bypasses RLS), can access this data. Nothing is publicly readable/writable via the anon key.

## Deployment

Deployed to Render as a single web service, connected directly to the GitHub repo for auto-deploy on push to `main`. Environment variables configured in Render's dashboard (see list above). Build command: `pip install -r requirements.txt`. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  
Note: Render's free tier spins down after ~15 minutes of inactivity. The first request after idling may take 10-30 seconds to respond while the service wakes up — this can occasionally cause a slash command's first attempt to time out; a retry immediately after succeeds.
  
Live URL: https://discord-slash-bot-d96o.onrender.com

## Testing it yourself

1. Join the test Discord server: https://discord.gg/k5zAC2e5T
2. Run `/status` or `/report <some text>` in any channel.
3. Watch the bot reply, and check the mirror channel `#notification` (`Channel ID: 1521960962582777969`) for the mirrored notification.
4. Visit the dashboard: `https://discord-slash-bot-d96o.onrender.com/login`
   - Email: `testadmin@gmail.com`
   - Password: `testadmin`

## Security notes

- Discord request signatures are verified on every request using Ed25519 (`pynacl`), on the raw request body, before any JSON parsing occurs.
- Interactions are deduplicated on Discord's `interaction_id` (unique DB constraint + application-level check).
- Secrets (bot token, public key, webhook URLs, Supabase keys, session secret) live only in environment variables — never committed, never sent to the client.
- Dashboard sessions use an HMAC-signed cookie with expiry; `httponly`, `secure`, and `samesite=lax` flags are set.
- Downstream failures (Discord API errors, mirror webhook errors) are caught and recorded (`status='failed'`, `error_message`) rather than silently dropped.

## What's not yet built (stretch goals)

- Interactive "Mark Resolved" button on `/report` replies — clicking it updates the message in-place and marks the report resolved in the log (exercises Discord's MESSAGE_COMPONENT interaction type, verified through the same signature-checked endpoint).
- AI-based triage of report text (Gemini)
- Multi-server support (schema supports it; UI doesn't yet)
- Structured retry mechanism beyond marking failures for visibility

See `AI_NOTES.md` for more on development process and decisions.