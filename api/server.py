"""
FastAPI application server.

Serves the Cadence API and static webapp.
"""

import logging

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    TODO: Implement
    - Initialize FastAPI
    - Configure CORS middleware
    - Mount static files (webapp/)
    - Register routes
    - Set up lifespan (startup/shutdown)
    """
    app = FastAPI(
        title="Cadence",
        description="Personal intelligence system — daily note pipeline",
        version="0.3.0",
    )

    # TODO: Add CORS middleware
    # TODO: Mount static files
    # TODO: Include routers
    # TODO: Add lifespan handler

    @app.get("/")
    async def root():
        """Redirect to webapp."""
        return RedirectResponse(url="/app/")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8420)
