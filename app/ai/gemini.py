"""
Minimal wrapper around Google's Gemini API (free tier via AI Studio) for
summarizing/tagging report text. Uses the REST endpoint directly via httpx
to avoid pulling in the full SDK for one call.
"""
import httpx
from app.config import GEMINI_API_KEY

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


async def summarize_report(text: str) -> str | None:
    """
    Returns a short one-line summary/tag for the given report text,
    or None if the AI call fails or no API key is configured
    (callers should treat None as 'skip AI, don't block the reply').
    """
    if not GEMINI_API_KEY:
        print("Gemini: GEMINI_API_KEY is not set — skipping AI step")
        return None

    prompt = (
        "You triage short user-submitted reports for a support bot. "
        "Given the report text below, respond with ONLY a single short line "
        "in the format: <category>: <one-sentence summary>. "
        "Categories to choose from: Bug, Outage, Feature Request, Question, Other. "
        "Do not add any other text.\n\n"
        f"Report: \"{text}\""
    )

    body = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(GEMINI_URL, headers=headers, params=params, json=body)
            if resp.status_code != 200:
                print(f"Gemini API error: {resp.status_code} {resp.text}")
                return None
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                print(f"Gemini API: no candidates in response: {data}")
                return None
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                print(f"Gemini API: no parts in response: {data}")
                return None
            return parts[0].get("text", "").strip()
    except Exception as e:
        print(f"Gemini API exception: {e}")
        return None