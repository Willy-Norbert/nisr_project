from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.data.store import DataNotPreparedError
from app.services.indicator_service import NotFoundError

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    description="Open agricultural intelligence platform built on NISR survey data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DataNotPreparedError)
async def not_prepared_handler(_: Request, exc: DataNotPreparedError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(api_router, prefix=settings.api_prefix)

# Serve the built React app (frontend/dist) from the same server when it exists, for single-service deployment.
if settings.frontend_dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dist_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        file = settings.frontend_dist_dir / path
        if path and file.is_file() and Path(file).resolve().is_relative_to(settings.frontend_dist_dir.resolve()):
            return FileResponse(file)
        return FileResponse(settings.frontend_dist_dir / "index.html")
