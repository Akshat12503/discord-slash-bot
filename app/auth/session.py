"""
Simple signed-cookie session for the admin dashboard.
We sign a payload (admin email + expiry) with SESSION_SECRET so it
can't be forged, without needing a server-side session store.
"""
import hmac
import hashlib
import base64
import json
import time
from app.config import SESSION_SECRET

SESSION_COOKIE_NAME = "admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 8  # 8 hours


def _sign(data: str) -> str:
    return hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()


def create_session_token(email: str) -> str:
    payload = json.dumps({"email": email, "exp": int(time.time()) + SESSION_TTL_SECONDS})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    signature = _sign(payload_b64)
    return f"{payload_b64}.{signature}"


def verify_session_token(token: str) -> dict | None:
    """Returns the payload dict if valid and not expired, else None."""
    if not token or "." not in token:
        return None
    payload_b64, signature = token.rsplit(".", 1)
    expected_sig = _sign(payload_b64)
    if not hmac.compare_digest(signature, expected_sig):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload