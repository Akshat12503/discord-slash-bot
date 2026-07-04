# Discord Slash-Command Bot

A web app + Discord bot that handles slash commands via Discord's HTTP Interactions API, logs every command to a database, replies in Discord, mirrors notifications to a second channel, exposes an admin dashboard to view the live log and configure command behavior, supports an interactive button follow-up, and runs report text through Gemini for AI triage.

## What it does

- `/status` — health-check style command, bot replies confirming it's online.
- `/report <text>` — submits a report:
  - A simple keyword rule flags it as "urgent" if it contains words like `urgent`, `asap`, `broken`, `down`, `critical`.
  - The report text is run through Gemini (`gemini-2.5-flash`) for a short category/summary tag (e.g. `Bug: ...`, `Outage: ...`), shown in the Discord reply, the mirrored message, and the dashboard log. If the Gemini call fails, times out, or is rate-limited, the report still processes normally — the AI tag is additive and never blocks the reply.
  - The reply includes a **"Mark Resolved"** button. Clicking it updates the message in-place (via Discord's `MESSAGE_COMPONENT` interaction type, verified through the same signature-checked endpoint) and marks the original report as resolved in the log.
- Every command interaction is:
  1. Verified via Discord's Ed25519 request signature (rejects forged/unsigned requests).
  2. Deduplicated on Discord's `interaction_id` (safe against retried deliveries).
  3. Acknowledged within Discord's ~3 second window via a deferred response, then processed in the background.
  4. Logged to a Postgres database (Supabase) with status tracking (`received` → `processed`/`failed`).
  5. Replied to in Discord (editing the deferred response, or synchronously updating the message for button clicks).
  6. Mirrored to a second Discord channel via webhook.
- An admin dashboard (behind login) shows a live command log — including AI summaries — and lets the admin toggle commands on/off and set a custom response template per command.

## Tech stack

- **Backend**: Python, FastAPI
- **Database + Auth**: Supabase (Postgres + Auth)
- **Frontend**: Server-rendered HTML (Jinja2 templates), light JS polling for live log updates
- **Notifications mirror**: Discord channel webhook
- **AI**: Google Gemini (`gemini-2.5-flash`, free tier via AI Studio)
- **Hosting**: Render (free tier)

## Project structure
app/
├── main.py                  # FastAPI app entrypoint
├── config.py                 # loads environment variables
├── ai/
│   └── gemini.py               # Gemini API wrapper (report triage)
├── auth/
│   ├── session.py             # signed-cookie session handling
│   ├── supabase_auth.py       # Supabase Auth login verification
│   └── dependency.py          # route protection helper
├── discord/
│   ├── verify.py               # Ed25519 signature verification
│   ├── commands.py             # slash command + button business logic
│   └── api.py                  # Discord REST API helpers (reply, mirror)
├── db/
│   ├── supabase_client.py      # Supabase client (service role)
│   ├── interactions_repo.py    # interactions table access
│   └── commands_repo.py        # commands_config table access
└── routes/
├── interactions.py         # POST /interactions — Discord's endpoint (commands + buttons)
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
- A free Gemini API key (Google AI Studio) — optional, only needed for the AI triage feature
- [ngrok](https://ngrok.com) (or similar) for local testing, since Discord requires a public HTTPS URL

### Setup

1. Clone the repo and create a virtual environment:
git clone https://github.com/Akshat12503/discord-slash-bot.git
cd discord-slash-bot
python -m venv venv
venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt

2. Copy `.env.example` to `.env` and fill in real values (see **Environment variables** below).

3. Create the database tables — run the SQL in the **Database schema** section below in your Supabase project's SQL Editor.

4. Register slash commands with Discord:
python scripts/register_commands.py

5. Run the app:
uvicorn app.main:app --port 8000
   (avoid `--reload` when testing anything signature-related — see **Known issues** below)

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
| `GEMINI_API_KEY` | Google AI Studio API key, used for `/report` AI triage (optional — reports still work without it) |

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
    ai_summary text,
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

**Known limitation:** Render's free tier spins down after ~15 minutes of inactivity. The first request after idling may take 10-30 seconds to respond while the service wakes up — this can occasionally cause a slash command's first attempt to time out ("The application did not respond" in Discord); a retry immediately after succeeds.

Live URL: `https://discord-slash-bot-d96o.onrender.com`

## Testing it yourself

1. Join the test Discord server: [INVITE LINK]
2. Run `/status` or `/report <some text>` in any channel.
3. For `/report`, click the **Mark Resolved** button that appears on the reply to see it update in-place.
4. Watch the bot reply (including the AI triage tag), and check the mirror channel `#notifications` for the mirrored notification.
5. Visit the dashboard: `https://discord-slash-bot-d96o.onrender.com/login`
   - Email: `testadmin@gmail.com`
   - Password: `testadmin`

## Security notes

- Discord request signatures are verified on every request using Ed25519 (`pynacl`), on the raw request body, before any JSON parsing occurs.
- Interactions are deduplicated on Discord's `interaction_id` (unique DB constraint + application-level check).
- Secrets (bot token, public key, webhook URLs, Supabase keys, session secret, Gemini API key) live only in environment variables — never committed, never sent to the client.
- Dashboard sessions use an HMAC-signed cookie with expiry; `httponly`, `secure`, and `samesite=lax` flags are set.
- Downstream failures (Discord API errors, mirror webhook errors, Gemini API errors) are caught and recorded (`status='failed'`, `error_message`) or silently skipped where appropriate (AI triage) rather than blocking the core flow.

## Known issues

- Running the FastAPI dev server with `uvicorn --reload` occasionally caused intermittent signature-verification failures during local testing (alternating 200/401 on identical requests), traced to the file-watcher process restarting mid-request. Workaround: run without `--reload` when testing Discord-facing endpoints locally. This does not affect the production deployment (Render doesn't use `--reload`).
- Render free-tier cold starts (see Deployment section above) can cause an occasional first-attempt timeout.

## What's not yet built (stretch goals)

- Modal form (an additional interaction type — deprioritized since buttons already exercise a second interaction type)
- Multi-server support (schema supports it via `servers`/`server_id`; UI/handlers currently assume a single server)
- The dashboard's command config (enable/disable, response template) is saved and readable in the database, but command handlers don't yet consult it at runtime — this is the next natural piece of work.
- Structured automatic retry for failed downstream calls (currently failures are recorded with an error message but not automatically retried)

See `AI_NOTES.md` for more on development process and decisions.AI_NOTES.md
