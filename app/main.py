from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import auth
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="LUNAR API",
    description="Backend API for the LUNAR space technology learning platform.",
    version="0.2.0",
    openapi_tags=[
        {"name": "health", "description": "Service health checks"},
        {"name": "auth", "description": "Registration, login, JWT, and Google OAuth"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.include_router(auth.router)


@app.get("/health", tags=["health"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}
