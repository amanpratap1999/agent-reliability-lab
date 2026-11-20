from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", description="Evidence-first reliability engineering for autonomous AI agents.")
app.include_router(health_router)
app.include_router(projects_router, prefix=settings.api_v1_prefix)
