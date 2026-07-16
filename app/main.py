from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import arena, auth, backoffice, laika, studio
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="LUNAR API",
    description="Backend API for the LUNAR space technology learning platform.",
    version="0.3.0",
    openapi_tags=[
        {"name": "health", "description": "Service health checks"},
        {"name": "auth", "description": "Registration, login, JWT, and Google OAuth"},
        {"name": "laika", "description": "LAIKA AI mentor (RAG + multi-provider LLM)"},
        {"name": "studio", "description": "Studio collections (notes, ideas, conversation trees)"},
        {"name": "arena", "description": "Arena missions (Blockly attempt save/load)"},
        {"name": "backoffice", "description": "Internal admin tools (knowledge ingest)"},
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
app.include_router(backoffice.router)
app.include_router(laika.router)
app.include_router(studio.router)
app.include_router(arena.router)


@app.get("/health", tags=["health"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}
