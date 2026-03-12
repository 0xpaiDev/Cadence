"""
FastAPI application server.

Serves the Cadence API and static webapp.
"""

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routes import get_config, router
from scripts.config import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    config = get_config()

    # Set up logging
    setup_logging(config.vault_path, config.log_level)
    logger.info("API server starting up")

    # Validate vault structure
    vault = Path(config.vault_path)
    if not vault.exists():
        logger.warning(f"Vault path {vault} does not exist — pipeline may not have run yet")
    else:
        logger.info(f"Vault path {vault} found")

        # Check required subdirectories
        required_dirs = ["state", "context", "drafts", "config", "logs"]
        for dirname in required_dirs:
            dirpath = vault / ".system" / dirname
            if not dirpath.exists():
                logger.warning(f"Missing directory: {dirpath} — will be created by pipeline")
            else:
                logger.debug(f"Found directory: {dirpath}")

        # Check day_state.json freshness
        day_state_path = vault / ".system" / "state" / "day_state.json"
        if day_state_path.exists():
            mtime = datetime.fromtimestamp(day_state_path.stat().st_mtime)
            today = date.today().isoformat()
            if mtime.date().isoformat() != today:
                logger.warning(f"Day state is stale (from {mtime.date()}, today is {today})")
            else:
                logger.info("Day state is fresh")
        else:
            logger.warning("Day state not found — pipeline has not run yet today")

        # Check draft existence
        draft_path = vault / ".system" / "drafts" / "today_draft.json"
        if not draft_path.exists():
            logger.warning("Today's draft not found — pipeline has not run yet today")
        else:
            logger.info("Today's draft exists")

    yield

    logger.info("API server shutting down")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Sets up CORS middleware, static file serving, and registers routes.
    """
    config = get_config()

    app = FastAPI(
        title="Cadence",
        description="Personal intelligence system — daily note pipeline",
        version="0.3.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    try:
        app.mount("/app", StaticFiles(directory="webapp/dist", html=True), name="webapp")
    except RuntimeError:
        logger.warning("webapp/dist/ directory not found — static file serving disabled (Phase 8)")

    app.include_router(router)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle unhandled exceptions and return JSON."""
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Check server logs for details."},
        )

    @app.get("/")
    async def root():
        """Redirect to webapp."""
        return RedirectResponse(url="/app/")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8420)
