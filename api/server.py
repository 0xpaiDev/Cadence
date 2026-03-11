"""
FastAPI application server.

Serves the Cadence API and static webapp.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routes import get_config, router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    config = get_config()
    vault = Path(config.vault_path)
    if not vault.exists():
        logger.warning(f"Vault path {vault} does not exist — pipeline may not have run yet")
    else:
        logger.info(f"Vault path {vault} found")
    yield


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

    @app.get("/")
    async def root():
        """Redirect to webapp."""
        return RedirectResponse(url="/app/")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8420)
