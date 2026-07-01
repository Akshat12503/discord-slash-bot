"""
Verifies admin login credentials against Supabase Auth (email/password).
"""
import httpx
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY


async def verify_login(email: str, password: str) -> bool:
    """Returns True if email/password match a valid Supabase Auth user."""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, json={"email": email, "password": password})
        return resp.status_code == 200