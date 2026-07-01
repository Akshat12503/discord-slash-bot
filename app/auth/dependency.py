"""
FastAPI dependency that protects dashboard routes.
Redirects to /login if there's no valid session cookie.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.auth.session import verify_session_token, SESSION_COOKIE_NAME


class RequireLogin:
    """
    Use as a dependency. Raises a redirect (via exception-free pattern)
    by returning None and letting the route handle it, OR we use it
    directly inside the route for simplicity here.
    """
    pass


def get_current_admin(request: Request) -> dict | None:
    """Returns the session payload if logged in, else None."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return verify_session_token(token)