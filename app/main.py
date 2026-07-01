from fastapi import FastAPI
from app.routes.interactions import router as interactions_router
from app.routes.auth_routes import router as auth_router
from app.routes.dashboard import router as dashboard_router

app = FastAPI(title="Discord Slash-Command Bot")

app.include_router(interactions_router)
app.include_router(auth_router)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Discord bot backend is running"}