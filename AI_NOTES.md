# AI_NOTES.md

## Tools and models used

I used Claude (Anthropic) as an AI pair-programmer throughout, working step-by-step from project scaffolding through deployment and two stretch goals (interactive buttons, Gemini AI triage). I made the decisions on stack, service choices, and when to move forward; Claude wrote the code files, explained Discord/Supabase/Gemini-specific mechanics I hadn't used before, and walked me through debugging real terminal/log output. I'd estimate roughly 65-70% of raw code was AI-drafted, but every file was reviewed, run, and verified against real output (Discord UI, Supabase tables, Render logs) before moving forward — nothing was accepted blind, and several real bugs were caught and fixed through that verification process (see below).

I have basic experience in C#/.NET/Angular but primarily use Python for DSA, so this was my first time building a FastAPI backend, integrating Discord's Interactions API, using Supabase, and calling Gemini's API.

## Key decisions I made

1. **FastAPI + server-rendered Jinja2 templates over a separate frontend.** Chose this instead of a split frontend/backend to minimize moving parts — one deployable app, no CORS complexity, fewer places to silently break during a time-boxed build. Given I hadn't used FastAPI before, keeping the surface area small mattered more than a fancier frontend.

2. **Discord channel webhook over Slack for the "mirror" notification.** I don't use Slack and didn't want to add an unfamiliar tool under time pressure. A second Discord channel webhook satisfies the same requirement with a tool I already understood.

3. **Deferred response + FastAPI BackgroundTasks for command processing**, rather than doing everything synchronously inside the request handler. Necessary to reliably stay within Discord's ~3 second response window regardless of how long Supabase writes, the Discord API, or Gemini take.

4. **AI triage designed to never block or fail the core flow.** `summarize_report()` catches every possible failure (missing key, timeout, rate limit, malformed response) and returns `None` rather than raising. The report still gets logged, replied to, and mirrored even if Gemini is completely unavailable — the AI step is strictly additive. This was a deliberate choice once I realized Gemini's free tier has real rate limits I could hit during normal testing.

5. **Signed-cookie sessions instead of a session-store or Supabase's client-side auth flow**, for the admin dashboard. Kept the auth surface fully server-side, appropriate for a single-admin use case.

## The hardest bug / wrong turn

There were two significant debugging episodes worth documenting honestly:

**1. Intermittent 200/401 on Discord's PING verification.** While registering the Interactions Endpoint URL, I saw alternating `200 OK` and `401 Unauthorized` on identical signed requests from Discord, with no code changes in between. Claude's first hypothesis (a `.env` formatting issue) was ruled out by directly checking the public key's length and format via a Python one-liner. The actual cause, found by isolating variables one at a time, was uvicorn's `--reload` file-watcher restarting mid-request — intermittently disrupting the worker process between reading the raw body and completing signature verification. Fix: run uvicorn without `--reload` when testing anything Discord-signature-related locally. After that, every test returned a clean single `200 OK`. Lesson: "intermittent binary failures with no code change" often points to process lifecycle, not logic bugs.

**2. A real signature-mismatch bug caught via the error-logging I'd built.** When adding the "Mark Resolved" button, both `handle_report` and `handle_status` needed new parameters and return values, but only `handle_report`'s signature actually got updated in one pass — `handle_status` was left on its old 2-argument version. The route called every handler the same way with 3 arguments, so every `/status` command started throwing `TypeError: handle_status() takes 2 positional arguments but 3 were given`. This didn't crash the app or lose the interaction — the `except Exception` block in `process_command` caught it and recorded `status='failed'` with the exact error message in the database, which is exactly what that error-tracking design was built for. I found the bug by reading the `error_message` column directly in Supabase, which pointed straight at the fix. This was a good validation that the "never silently lose an interaction" requirement wasn't just theoretical — it directly helped debug a real, self-inflicted bug within minutes instead of guessing from vague symptoms.

**A closely related issue** while adding the Gemini step: `ai_summary` stayed `NULL` with no error logged at all. I isolated the problem by testing the Gemini API key directly via a standalone PowerShell request against the REST endpoint, confirming the key and model both worked (`200 OK` with a real response) completely independent of my app. That ruled out the API/key and pointed at the app's environment wiring on Render specifically (local `.env` values don't automatically transfer to Render — they have to be added separately in Render's dashboard). Also hit a genuine `429 Too Many Requests` on `gemini-2.0-flash`'s free tier during testing and switched to `gemini-2.5-flash`, which resolved it.

## What I'd improve or add with more time

- Wire the dashboard's command config (enabled/disabled, response template) into actual runtime behavior — currently it reads/writes to the database correctly but handlers don't consult it yet.
- Add a modal form as a third interaction type (e.g. a longer structured report form).
- Add structured logging and an automatic retry mechanism for failed downstream calls, rather than just recording the failure for visibility.
- Multi-server support — the schema (`servers` table, `server_id` foreign keys) was designed with this in mind from the start, but the UI/handlers currently assume a single server.
- A background sweep for interactions stuck at `status='received'` (e.g. if a background task gets killed mid-flight by a platform restart before it can mark itself `processed` or `failed`) — I observed this could theoretically happen during a Render redeploy mid-request, though I didn't hit a confirmed case of it in testing.

## Example prompt excerpt

When debugging the Gemini `ai_summary` staying `NULL` with zero errors logged, part of my prompt to Claude was:

Claude's response was to stop guessing at the app code and instead have me test the raw API key directly against Gemini's endpoint via PowerShell, independent of the app entirely, which immediately confirmed the key/model worked and redirected the investigation to Render's environment variable configuration instead of more app-code changes. That "isolate the external dependency first, before re-reading your own code again" approach was the most useful debugging pattern across the whole project.
