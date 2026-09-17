import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.exc import SQLAlchemyError

from app.ai.openrouter_client import AIError
from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import CommerceError
from app.db.session import engine
from app.observability.telemetry import API_LATENCY, configure_logging, request_id
from app.security.rate_limit import RateLimiter

configure_logging()
settings = get_settings()
limiter = RateLimiter(settings.rate_limit_per_minute)
LOG = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(title="ShopPilot AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.include_router(router)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    identifier = str(uuid4())
    context = request_id.set(identifier)
    started = time.perf_counter()
    try:
        if request.url.path not in {
            "/api/v1/health",
            "/api/v1/ready",
            "/metrics",
        } and not limiter.allow(request.client.host if request.client else "unknown"):
            return JSONResponse(
                {"message": "Too many requests. Please wait a moment."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        if int(request.headers.get("content-length", "0")) > 32768:
            return JSONResponse({"message": "Request body is too large."}, status_code=413)
        response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": identifier,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            }
        )
        route = getattr(request.scope.get("route"), "path", "unmatched")
        API_LATENCY.labels(request.method, route, response.status_code).observe(
            time.perf_counter() - started
        )
        LOG.info(
            "api_request",
            extra={
                "safe_fields": {
                    "route": route,
                    "status": response.status_code,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                }
            },
        )
        return response
    finally:
        request_id.reset(context)


@app.exception_handler(CommerceError)
async def commerce_error(request: Request, error: CommerceError) -> JSONResponse:
    return JSONResponse({"message": error.message}, status_code=error.status_code)


@app.exception_handler(AIError)
async def ai_error(request: Request, error: AIError) -> JSONResponse:
    return JSONResponse({"message": str(error)}, status_code=503)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
    LOG.error("database_unavailable")
    return JSONResponse(
        {
            "message": "The store is temporarily unavailable. Check database connectivity and migrations."
        },
        status_code=503,
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
    LOG.error("unexpected_error", extra={"safe_fields": {"error_type": type(error).__name__}})
    return JSONResponse({"message": "ShopPilot is temporarily unavailable."}, status_code=500)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
