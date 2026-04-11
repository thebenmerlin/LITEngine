import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from utils.logger import setup_logger, get_logger
from utils.cache import cache
from services.embedder import embedder_service
from services.kanoon import kanoon_service

# Routers
from routers import precedent, facts, graph, simulation

logger = get_logger(__name__)

_index_loaded = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    global _index_loaded

    # ---- Startup --------------------------------------------------------
    settings = get_settings()
    setup_logger(settings.LOG_LEVEL)

    # Ensure logs and fixtures directories exist
    os.makedirs("logs", exist_ok=True)
    os.makedirs("fixtures", exist_ok=True)

    # Configure cache TTL
    cache._ttl = settings.CACHE_TTL

    # Startup log — never the key itself, just presence
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"CORS origins: {settings.ALLOWED_ORIGINS}")
    logger.info(f"Cache TTL: {settings.CACHE_TTL}s")
    logger.info(f"HF API key: {'set' if settings.hf_key_set else 'not set'}")

    # Load FAISS precedent index
    _index_loaded = embedder_service.load_index()
    if _index_loaded:
        stats = embedder_service.get_stats()
        logger.info(
            f"FAISS index loaded: {stats['total_documents']} documents, "
            f"{embedder_service.total_vectors} vectors, "
            f"{stats['index_size_bytes'] / 1024:.1f} KB"
        )
    else:
        logger.info("FAISS index not loaded — semantic search will use Kanoon fallback")

    yield

    # ---- Shutdown -------------------------------------------------------
    logger.info("Shutting down — saving FAISS index…")
    embedder_service.save_index()
    cache.clear()
    await embedder_service.close()
    await kanoon_service.close()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered legal intelligence system for Indian law",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware — production vs dev
    if settings.IS_PRODUCTION:
        origins = settings.allowed_origins_list
        logger.info(f"Production CORS: allowing {len(origins)} origin(s): {origins}")
    else:
        origins = settings.cors_origins  # ["*"] in dev

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health endpoint (root level)
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "healthy",
        }

    # Readiness endpoint (for Render health checks)
    @app.get("/api/v1/health/ready")
    async def health_ready():
        """Readiness probe — returns readiness of all subsystems."""
        return {
            "ready": True,
            "index_loaded": _index_loaded,
            "hf_key_set": settings.hf_key_set,
        }

    # Register routers with /api/v1 prefix
    app.include_router(precedent.router, prefix="/api/v1")
    app.include_router(facts.router, prefix="/api/v1")
    app.include_router(graph.router, prefix="/api/v1")
    app.include_router(simulation.router, prefix="/api/v1")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
