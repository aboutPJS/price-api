"""
Main application entry point for the Energy Price API service.
Initializes FastAPI app, database, scheduler, and starts the service.
"""

import asyncio
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.api.routes import router as api_router
from src.config import settings
from src.database.service import db_service
from src.logging_config import setup_logging
from src.scheduler.simple_scheduler import simple_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown procedures.
    """
    # Startup
    setup_logging()
    await db_service.init_database()
    await simple_scheduler.start()
    
    yield
    
    # Shutdown
    await simple_scheduler.stop()
    await db_service.close()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title="Energy Price API",
        description="Dynamic Energy Price Optimization System - Andel Energi Integration",
        version="1.0.0",
        docs_url="/docs" if settings.api_debug else None,
        redoc_url="/redoc" if settings.api_debug else None,
        lifespan=lifespan,
    )

    # Include API routes
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
