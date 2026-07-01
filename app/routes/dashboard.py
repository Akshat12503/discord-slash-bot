"""
Admin dashboard: interaction log + command configuration.
Protected by the session cookie set at /login.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependency import get_current_admin
from app.db.commands_repo import get_all_command_configs, get_recent_interactions, upsert_command_config

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/login", status_code=303)

    interactions = get_recent_interactions()
    configs = get_all_command_configs()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "admin_email": admin["email"],
            "interactions": interactions,
            "configs": configs,
        },
    )


@router.get("/dashboard/data")
async def dashboard_data(request: Request):
    """JSON endpoint the dashboard polls for live-ish updates."""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    interactions = get_recent_interactions()
    return {"interactions": interactions}


@router.post("/dashboard/config")
async def update_config(
    request: Request,
    command_name: str = Form(...),
    enabled: bool = Form(False),
    response_template: str = Form(""),
):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/login", status_code=303)

    upsert_command_config(command_name, enabled, response_template)
    return RedirectResponse(url="/dashboard", status_code=303)