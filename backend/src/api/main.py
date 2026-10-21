"""AuditIt FastAPI application main entrypoint."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import documents, graph, health, query, samples


def create_app() -> FastAPI:
    """Factory creating configured FastAPI instance with all routes and CORS."""
    app = FastAPI(
        title="AuditIt API",
        description="Graph-based financial audit and causal analysis platform API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # Configurable CORS for production deployments (defaults to * for development)
    raw_origins = os.getenv("CORS_ORIGINS", "*")
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()] if raw_origins != "*" else ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers under /api
    app.include_router(health.router, prefix="/api")
    app.include_router(samples.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(query.router, prefix="/api")

    @app.get("/")
    def root():
        return {
            "name": "AuditIt API",
            "version": "0.1.0",
            "docs": "/docs",
            "status": "online",
        }

    return app


app = create_app()
