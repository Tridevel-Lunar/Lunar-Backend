# LUNAR Backend

Python **FastAPI** — API gateway, ฟิสิกส์อวกาศ, simulation, LAIKA (LLM + RAG)

## Docs

- [docs/development.md](docs/development.md) — tech stack, conventions
- [../docs/docker-dev.md](../docs/docker-dev.md) — Docker Compose (workspace root, dev only)

## Quick Start

### Docker (จาก `Lunar/` root)

```bash
docker compose up --build backend
```

### Local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000 · Health: http://localhost:8000/health

## Stack (สรุป)

| หมวด | เครื่องมือ |
|------|-----------|
| Language | Python 3.11+ |
| API | FastAPI |
| Database | PostgreSQL |
| Orbital mechanics | Poliastro / PyEphem |
| LAIKA LLM | Gemini API (Google AI SDK) |
| RAG | LangChain หรือ LlamaIndex |
