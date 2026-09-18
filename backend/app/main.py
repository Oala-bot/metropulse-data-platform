import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response

from backend.app.api.routes import router
from backend.app.core.config import Settings
from backend.app.database.session import create_database_engine
from backend.app.schemas.analytics import ErrorResponse, Health

LOGGER = logging.getLogger("metropulse.api")
LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.propagate = False


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: list[dict[str, object]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
                "details": details or [],
            }
        },
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings or Settings()
        app.state.engine = create_database_engine(app.state.settings)
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(
        title="MetroPulse API",
        version="0.1.0",
        lifespan=lifespan,
        responses={code: {"model": ErrorResponse} for code in [401, 404, 409, 422, 500, 503]},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=(settings or Settings()).cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            LOGGER.error(
                json.dumps({"event": "unhandled_error", "request_id": request.state.request_id})
            )
            response = error_response(request, 500, "internal_error", "Unexpected server error")
        response.headers["X-Request-ID"] = request.state.request_id
        LOGGER.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - start) * 1000, 2),
                }
            )
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        codes = {
            401: "unauthorized",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            503: "service_unavailable",
        }
        return error_response(
            request, exc.status_code, codes.get(exc.status_code, "http_error"), str(exc.detail)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"location": list(e["loc"]), "message": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return error_response(
            request, 422, "validation_error", "Invalid request parameters", details
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        LOGGER.error(
            json.dumps(
                {
                    "event": "database_error",
                    "type": type(exc).__name__,
                    "request_id": request.state.request_id,
                }
            )
        )
        return error_response(
            request, 503, "database_unavailable", "Database or warehouse is unavailable"
        )

    @app.get("/health", response_model=Health)
    def health(request: Request) -> Response:
        try:
            with request.app.state.engine.connect() as connection:
                ready = connection.execute(
                    text("SELECT to_regclass('analytics.fact_trip')")
                ).scalar_one()
            result = Health(
                status="ok" if ready else "degraded",
                database="ok",
                warehouse="ready" if ready else "not_built",
            )
            return JSONResponse(jsonable_encoder(result), status_code=200 if ready else 503)
        except SQLAlchemyError:
            result = Health(status="unavailable", database="unavailable", warehouse="unknown")
            return JSONResponse(jsonable_encoder(result), status_code=503)

    app.include_router(router)
    return app


app = create_app()
