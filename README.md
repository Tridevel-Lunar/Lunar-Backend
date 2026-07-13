# LUNAR Backend

Python **FastAPI** — API gateway, authentication, ฟิสิกส์อวกาศ, simulation, LAIKA (LLM + RAG)

> Repo นี้เป็น **git submodule** ใน workspace [lunar-dev](https://github.com/Tridevel-Lunar/lunar-dev) — แนะนำรันทั้ง stack จาก workspace root

## Docs

- [docs/development.md](docs/development.md) — tech stack, conventions, env, testing
- [docs/api.md](docs/api.md) — auth API contract summary
- [docs/laika.md](docs/laika.md) — LAIKA / RAG
- [../frontend/docs/development.md](../frontend/docs/development.md) — frontend + Vite proxy
- Workspace Docker: [../../docs/docker-dev.md](../../docs/docker-dev.md)

## Quick Start

### Docker (recommended)

จาก workspace root (`lunar-dev`):

```bash
cp .env.example .env
docker compose up --build
```

- App + API proxy: http://localhost:3000 (`/api` → backend)
- Swagger: http://localhost:3000/api/docs
- Backend **ไม่** expose port ออก host
- PostgreSQL: `localhost:5432` (user/db: `lunar`)

รายละเอียด: [../../docs/docker-dev.md](../../docs/docker-dev.md)

### Local (uvicorn — optional)

```bash
python -m venv .lunar-be-venv
# Windows: .lunar-be-venv\Scripts\activate
pip install -r requirements.txt
```

สร้าง `backend/.env` จากค่าใน [docs/development.md](docs/development.md#environment) — ต้องมี **PostgreSQL** ที่ `localhost:5432` (หรือรันแค่ `postgres` จาก compose)

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000 · Health: `/health` · Swagger: `/docs`  
Frontend ที่ port 3000 proxy `/api` → backend อัตโนมัติ

## Tests

```bash
pytest              # ทั้งหมด — ไม่ต้อง Postgres (SQLite in-memory)
pytest -v
pytest tests/test_auth.py
```

ดู [docs/development.md](docs/development.md#testing)

## Implemented today

| หมวด | สถานะ |
|------|--------|
| Auth (email/password) | ✓ register, login, logout, `/auth/me` |
| Session | ✓ httpOnly cookie `lunar_token` + Bearer JWT |
| Google Sign-In | ✓ One Tap (`POST /auth/google/onetap`) + redirect OAuth (`GET /auth/google`) |
| Users DB | ✓ PostgreSQL + Alembic migrations |
| Health | ✓ `GET /health` |
| LAIKA / Studio | ✓ (ดู [docs/laika.md](docs/laika.md)) |

## Stack (สรุป)

| หมวด | เครื่องมือ |
|------|-----------|
| Language | Python 3.11+ |
| API | FastAPI, Uvicorn |
| Database | PostgreSQL + pgvector, SQLAlchemy, Alembic |
| Auth | passlib/bcrypt, python-jose, Authlib, google-auth |
| LAIKA | LangChain RAG + Gemini / Groq / Ollama |

Production deploy (Render Docker): [`Dockerfile`](Dockerfile) — ดู [docs/development.md](docs/development.md#deploy-render--docker)
