from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .api import ai, cicd, cloud, engineering, insights, platform


BASE_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_FILE = BASE_DIR / "dashboard" / "index.html"

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "ArcMatrix: enterprise engineering, cloud, CI/CD, and AI intelligence API."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(engineering.router)
app.include_router(cicd.router)
app.include_router(cloud.router)
app.include_router(ai.router)
app.include_router(insights.router)
app.include_router(platform.router)


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(DASHBOARD_FILE)
