# LUNAR Backend

Python **FastAPI** — API gateway, authentication, ฟิสิกส์อวกาศ, simulation, LAIKA (LLM + RAG)

## Docs

- [docs/development.md](docs/development.md) — tech stack, conventions, env, testing
- [docs/api.md](docs/api.md) — auth API contract summary
- [../Frontend/docs/development.md](../Frontend/docs/development.md) — frontend dev + Vite proxy

## Quick Start

### Local (recommended for dev)

```bash
python -m venv .lunar-be-venv
# Windows: .lunar-be-venv\Scripts\activate
pip install -r requirements.txt
```

สร้าง `.env` จากค่าใน [docs/development.md](docs/development.md#environment) — ต้องมี **PostgreSQL** รันที่ `localhost:5432`

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000 · Health: http://localhost:8000/health · Swagger: http://localhost:8000/docs

Frontend (`npm run dev` ที่ port 3000) proxy `/api` → backend อัตโนมัติ

### Docker (optional)

```bash
# จาก workspace root — เมื่อมี docker-compose.yml
docker compose up --build backend
```

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
| Orbital / LAIKA / simulation | planned |

## Stack (สรุป)

| หมวด | เครื่องมือ |
|------|-----------|
| Language | Python 3.11+ |
| API | FastAPI, Uvicorn |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Auth | passlib/bcrypt, python-jose, Authlib, google-auth |
| Orbital mechanics | Poliastro / PyEphem (planned) |
| LAIKA LLM | Gemini API (planned) |
| RAG | LangChain หรือ LlamaIndex (planned) |

Production deploy (Render Docker): [`Dockerfile`](Dockerfile) — ดู [docs/development.md](docs/development.md#deploy-render--docker)
