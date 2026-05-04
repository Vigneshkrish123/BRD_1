"""
BRD Agent — Uvicorn entrypoint.
"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from loguru import logger

    logger.info(
        "BRD Agent starting",
        env=settings.app_env,
        model=settings.azure_foundry_model,
        template=settings.brd_template_path,
    )
    yield
    logger.info("BRD Agent shutting down")


app = FastAPI(
    title="BRD Agent",
    version="1.0.0",
    description="Converts meeting transcripts into filled BRD Word documents.",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "env": settings.app_env})


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
        log_config=None,  # Loguru handles logging
    )
