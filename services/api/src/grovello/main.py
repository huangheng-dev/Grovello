import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from grovello.api.router import api_router
from grovello.config import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Grovello-Dev-Session",
            "X-Grovello-Dev-Subject",
            "X-Request-ID",
            "X-Workspace-ID",
        ],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, _exception: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "requestId": request.state.request_id,
            },
        )

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
