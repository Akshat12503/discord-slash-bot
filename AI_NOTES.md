# AI_NOTES.md

## Tools and models used

I used Claude (Anthropic) as an AI pair-programmer throughout, working step-by-step from project scaffolding through deployment. Roughly: I made the decisions on stack, service choices, and when to move forward; Claude wrote the code files, explained Discord/Supabase-specific mechanics I hadn't used before, and walked me through debugging terminal output and error messages. I'd estimate ~70% of raw code was AI-drafted, but every file was reviewed, run, and verified against real output (Discord UI, Supabase tables, uvicorn/ngrok logs) before moving forward — nothing was accepted blind.

I have basic experience in C#/.NET/Angular but primarily use Python for DSA, so this was my first time building a FastAPI backend, integrating Discord's Interactions API, and using Supabase.

## Key decisions I made

1. **FastAPI + server-rendered Jinja2 templates over a separate frontend.** I chose this instead of a split frontend/backend (e.g. React + separate API) to minimize moving parts — one deployable app, no CORS complexity, and fewer places for something to silently break during the ~72 hour window. Given I hadn't used FastAPI before, keeping the surface area small mattered more than a fancier frontend.

2. **Discord channel webhook over Slack for the "mirror" notification.** I don't use Slack and didn't want to add an unfamiliar tool under time pressure. A second Discord channel webhook satisfies the same requirement (external mirror notification) with a tool I already understood.

3. **Deferred response + FastAPI BackgroundTasks for command processing**, rather than trying to do everything synchronously inside the request handler. This was necessary to reliably stay within Discord's ~3 second response window regardless of how long the Supabase writes or Discord API calls take — and it directly maps to the "respect the 3-second window" requirement in the brief.

4. **Signed-cookie sessions instead of a session-store or Supabase's client-side auth flow**, for the admin dashboard. Kept the auth surface simple and fully server-side, appropriate for a single-admin use case rather than a multi-user product.

## The hardest bug / wrong turn

While verifying the Discord Interactions Endpoint URL, I saw an inconsistent pattern in the logs: alternating `200 OK` and `401 Unauthorized` responses to the *same* signed PING request from Discord, with no code changes in between. This was confusing because the signature verification logic looked correct and the public key was confirmed to be exactly 64 hex characters.

Claude's first hypotheses (double-quoting/copy-paste issues in `.env`) turned out to be ruled out once I verified the key length and format directly via a Python one-liner. The actual cause, found by isolating variables one at a time, was **uvicorn's `--reload` file-watcher process restarting mid-request** — something intermittently disrupted the running worker process's state between reading the raw request body and completing the signature check, causing sporadic failures under `--reload` even with correct code.

The fix: run uvicorn *without* `--reload` while testing anything Discord-signature-related. After that, ten consecutive Discord PING/interaction tests all returned a clean single `200 OK`. This was a good reminder that "intermittent binary failures with no code change" often points to process lifecycle/environment issues rather than logic bugs — and that clearing extra variables (dev auto-reload) one at a time was faster than re-reading the signature verification code again and again.

## What I'd improve or add with more time

- Add the button/modal stretch goal (a follow-up interactive component after `/report`, e.g. a "Mark Resolved" button).
- Wire the AI stretch goal: pass `/report` text through Gemini for a one-line summary/tag, shown in both the Discord reply and the dashboard.
- Make the dashboard's command config actually drive runtime behavior (currently the config UI reads/writes to the database correctly, but the command handlers don't yet consult `commands_config.enabled` / `response_template` when processing — that wiring is the next natural step).
- Add structured logging and a visible retry mechanism for failed downstream calls (currently failures are recorded with an error message but not automatically retried).
- Multi-server support — the schema (`servers` table, `server_id` foreign keys) was designed with this in mind from the start, but the UI currently assumes a single server.

## Example prompt excerpt

When debugging the intermittent 401/200 issue, part of my prompt to Claude was://| I don't know anything, so if there are any signs of lurking complexity, help me step by step and tell me exactly what to run and check. Here's the terminal output showing 200 then 401 for the same URL... [pasted ngrok + uvicorn logs].