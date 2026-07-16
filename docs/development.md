# LUNAR Backend

Python **FastAPI** — API server เชื่อม frontend กับ auth, ฟิสิกส์, simulation, และ LAIKA

**Product context:** [../frontend/docs/concept.md](../frontend/docs/concept.md) · [functional-spec](../frontend/docs/functional-spec.md)  
**API contract:** [api.md](api.md)  
**Frontend dev:** [../frontend/docs/development.md](../frontend/docs/development.md)  
**Workspace Docker:** [../../docs/docker-dev.md](../../docs/docker-dev.md)

## บทบาทหลัก

| หน้าที่ | รายละเอียด | สถานะ |
|---------|------------|--------|
| **Authentication** | register, login, logout, refresh, JWT + httpOnly cookies, Google Sign-In | ✓ |
| **API Gateway** | รับ request จาก frontend — auth, studio, laika, **arena attempt save/load** | live (runs/sim planned) |
| **Orbital / Physics** | คำนวณสมการฟิสิกส์อวกาศ, วงโคจร, power budget | planned |
| **Logging** | โครงสร้างข้อมูล log จากจำลอง | planned |
| **LAIKA** | LLM (Gemini/DeepSeek/Ollama) + RAG ให้คำแนะนำผู้เรียน | ✓ |
| **Satellite imagery** | ส่งข้อมูลภาพดาวเทียมกลับ frontend | planned |

## Tech Stack

### ภาษา

| ภาษา | การใช้งาน |
|------|-----------|
| **Python** | ภาษาหลัก — API, auth, สมการฟิสิกส์อวกาศ, วงโคจร |

### Framework & Libraries (ใช้อยู่)

| เครื่องมือ | บทบาท |
|-----------|--------|
| **FastAPI** | API server |
| **PostgreSQL** + **SQLAlchemy** + **Alembic** | users, migrations |
| **passlib** / **bcrypt** | password hashing |
| **python-jose** | JWT access tokens |
| **Authlib** | Google OAuth redirect flow (`/auth/google`) |
| **google-auth** | verify GIS / One Tap credential JWT |
| **pydantic-settings** | `.env` configuration |

### วางแผน

| เครื่องมือ | บทบาท |
|-----------|--------|
| **Poliastro** | orbital mechanics, Kepler |
| **PyEphem** | ephemeris / ตำแหน่งดาราศาสตร์ |
| **Gemini API** / **DeepSeek API** / **Ollama** | LLM providers สำหรับ LAIKA |
| **LangChain** | RAG pipeline |

> ไม่ใช้ Node.js/Express — backend เป็น Python + FastAPI เท่านั้น

## Authentication

### Session cookies

| Cookie | ชนิด | อายุ (default) | บทบาท |
|--------|------|----------------|--------|
| `lunar_token` | JWT access token | 30 นาที | ยืนยันตัวตน API request |
| `lunar_refresh` | Opaque token (hash ใน DB) | 7 วัน | แลก access token ใหม่ผ่าน `/auth/refresh` |

Refresh token เก็บในตาราง `refresh_tokens` — rotate ทุกครั้งที่ refresh สำเร็จ; logout revoke token ใน DB

### Email / password

- `POST /auth/register` — สร้าง user, คืน JWT + Set-Cookie (access + refresh)
- `POST /auth/login` — ตรวจ email/password, Set-Cookie
- `POST /auth/refresh` — แลก refresh cookie เป็น access ใหม่ + rotate refresh
- `POST /auth/logout` — revoke refresh token, ลบ cookies ทั้งคู่
- `GET /auth/me` — ต้องมี Bearer token หรือ cookie `lunar_token`

### Google Sign-In

สอง flow บน backend:

| Flow | Endpoint | ต้องการ env |
|------|----------|-------------|
| **One Tap / GIS button** (frontend ใช้หลัก) | `POST /auth/google/onetap` | `GOOGLE_CLIENT_ID` |
| **Browser redirect** (optional) | `GET /auth/google` → `/auth/google/callback` | `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` + `GOOGLE_REDIRECT_URI` |

One Tap flow:

```
Frontend credential JWT
  → verify_google_id_token()  (google-auth, audience = GOOGLE_CLIENT_ID)
  → get_or_create_google_user()  (link by google_sub or email)
  → Set-Cookie lunar_token + lunar_refresh
```

Redirect callback ตรวจ `email_verified` เช่นเดียวกับ One Tap

### Account linking

- ค้นหา user จาก `google_sub` ก่อน
- ถ้ามี email เดิมแต่ยังไม่มี `google_sub` → link บัญชี
- ถ้า email ผูกกับ Google account อื่นแล้ว → `409 Conflict`

### AI (LAIKA)

```
ผู้เรียน → Frontend → FastAPI → [RAG: LangChain] → LLM provider (Gemini/Groq/Ollama) → คำตอบ + sources
```

- RAG ลด hallucination — ตอบจากเอกสารวิศวกรรมอวกาศจริง
- Assist prompt รวมชื่อผู้เรียน (จาก auth), เวลาปัจจุบัน, timestamp ประวัติแชท, และคำแนะนำความต่อเนื่องของบทสนทนา
- API keys อยู่ใน workspace `.env` / `backend/.env` เท่านั้น — ห้าม commit
- รายละเอียดเต็ม: **[docs/laika.md](laika.md)** (providers, ingest, env)

## โครงสร้างปัจจุบัน

```
backend/
├── alembic/                    # migrations
├── app/
│   ├── api/
│   │   ├── deps.py             # get_current_user, admin guard
│   │   └── routes/
│   │       ├── auth.py         # register, login, logout, refresh, me, google/*
│   │       ├── laika.py        # assist, stream, context usage
│   │       ├── studio.py       # collections, conversation, branch map
│   │       └── backoffice.py   # knowledge admin
│   ├── core/config.py, cookies.py, security.py
│   ├── db/session.py, base.py
│   ├── models/user.py, refresh_token.py, knowledge_*.py, studio_collection.py
│   ├── schemas/auth.py, laika.py, studio.py, backoffice.py
│   ├── services/
│   │   ├── auth.py, google_auth.py, refresh_token.py, rbac.py, user_admin.py
│   │   ├── laika.py, studio.py, studio_tree.py, knowledge/
│   │   └── rag/                # providers, retriever, chain, context_window
│   └── main.py
├── data/knowledge/             # RAG corpus + manifest.yaml
├── scripts/                    # ingest, sync manifest
├── docs/api.md, laika.md, development.md
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_laika.py, test_laika_context.py, test_laika_providers.py
│   ├── test_studio.py, test_backoffice.py, test_rbac.py
│   └── test_health.py, test_security.py
├── Dockerfile, Dockerfile.dev
├── requirements.txt
└── .env                        # ไม่ commit
```

## Environment

**Docker (recommended):** ตั้งค่าใน workspace root `.env` — compose inject เข้า backend container  
แม่แบบ: [../../.env.example](../../.env.example) · ดู [../../docs/docker-dev.md](../../docs/docker-dev.md)

**Local uvicorn:** สร้าง `backend/.env` (ห้าม commit) ด้วยตัวแปรชุดเดียวกัน

| Variable | Default (dev) | หมายเหตุ |
|----------|---------------|----------|
| `DATABASE_URL` | `postgresql+psycopg://lunar:lunar@localhost:5432/lunar` | ใน Docker compose ตั้งเป็น host `postgres` |
| `SECRET_KEY` | — | เปลี่ยนใน production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | อายุ JWT access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | อายุ refresh token |
| `CORS_ORIGINS` | `http://localhost:3000` | คั่นหลาย origin ด้วย comma |
| `FRONTEND_URL` | `http://localhost:3000` | redirect หลัง Google OAuth callback |
| `GOOGLE_CLIENT_ID` | _(ว่าง)_ | เปิด Google Sign-In — **ค่าเดียวกับ frontend** (public client ID) |
| `GOOGLE_CLIENT_SECRET` | _(ว่าง)_ | redirect OAuth เท่านั้น — ห้ามส่งไป frontend |
| `GOOGLE_REDIRECT_URI` | `http://localhost:3000/api/auth/google/callback` | ผ่าน Vite proxy (ต้องตรงกับ Google Cloud Console) |
| `AUTH_COOKIE_SECURE` | `false` | ตั้ง `true` ใน production (HTTPS) |

### Google Cloud Console (dev)

1. OAuth client type: **Web application**
2. **Authorized JavaScript origins:** `http://localhost:3000`, `http://127.0.0.1:3000`
3. **Authorized redirect URIs:** `http://localhost:3000/api/auth/google/callback` (ถ้าใช้ redirect flow)
4. OAuth consent screen: **External** + test users (ถ้าอยู่ใน Testing mode)

## Commands

```bash
# Docker — จาก workspace root
docker compose up --build
docker compose exec backend alembic upgrade head
docker compose exec backend pytest

# Local uvicorn
python -m venv .lunar-be-venv
.lunar-be-venv\Scripts\activate          # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Tests (ไม่ต้อง Postgres)
pytest
pytest -v
pytest tests/test_auth.py
```

**API URL:**

| โหมด | Base URL |
|------|----------|
| Docker | http://localhost:3000/api (Vite proxy) |
| Local uvicorn | http://localhost:8000 |

Frontend เรียกผ่าน `/api` — Vite proxy strip prefix (`/api/auth/login` → `/auth/login`)

## API

- **Swagger (Docker):** http://localhost:3000/api/docs
- **Swagger (local uvicorn):** http://localhost:8000/docs
- **ReDoc:** `/redoc` (ภายใต้ base เดียวกัน)
- Contract summary: [api.md](api.md)

## Testing

Backend ใช้ **pytest** + FastAPI `TestClient` — unit/API tests ใช้ **SQLite in-memory** (ไม่ต้องรัน Postgres)

### โครงสร้าง

| ไฟล์ | ครอบคลุม |
|------|-----------|
| `tests/conftest.py` | SQLite DB, `client`, `auth_headers`, `google_client_id`, `google_token_payload` |
| `tests/test_health.py` | `GET /health` |
| `tests/test_security.py` | password hash/verify, JWT create/decode |
| `tests/test_auth.py` | register, login, cookies, refresh rotation, `/auth/me`, logout, Google One Tap (mocked), 401/409/503 |
| `tests/test_laika.py` | `/laika/health`, `/laika/assist`, sources[], 503 when disabled |
| `tests/test_laika_context.py` | Context usage, history timestamps, learner name in prompt |
| `tests/test_studio.py` | Studio collections + conversation/branch APIs |
| `tests/test_laika_providers.py` | Provider factory validation |

### หมายเหตุ

- เทส override `get_db` — ไม่แตะ PostgreSQL จริง
- Google tests mock `verify_google_id_token` — ไม่เรียก Google API จริง
- env เริ่มต้นในเทส: `GOOGLE_CLIENT_*` ว่าง (503 when unconfigured)
- เพิ่ม endpoint ใหม่ → เพิ่มเทสใน `tests/` ก่อน merge PR

### Manual / E2E

1. `docker compose up --build` จาก workspace root (หรือ Postgres + uvicorn แยก)
2. Swagger: http://localhost:3000/api/docs — register → `/auth/me`
3. App: http://localhost:3000/register → Google หรือ email → `/space`

**ข้อผิดพลาดที่พบบ่อย:** Google login ผ่าน GIS แล้ว แต่ `POST /auth/google/onetap` 500 — มักเป็น **PostgreSQL ไม่รัน**

## Code Style

- Python 3.11+
- Type hints บน function signatures
- Async endpoints สำหรับ OAuth redirect; sync สำหรับ DB-heavy auth handlers
- Comments และ docstrings ภาษา**อังกฤษ**
- ชื่อ product: **LAIKA**, **Space**, **Arena**, **Studio**

## Frontend ↔ Backend

- ไม่ import ข้าม repo — HTTP เท่านั้น
- Session: httpOnly cookies `lunar_token` + `lunar_refresh` (`credentials: "include"` บน frontend)
- Access token หมดอายุ → frontend เรียก `POST /auth/refresh` อัตโนมัติ (ดู `frontend/src/lib/auth.ts`, `api.ts`)
- ฟิสิกส์/วงโคจรรันฝั่ง backend; frontend แสดงผล
- Blockly block definitions / AST: FE emits JSON AST; BE stores draft via `/arena` (in-memory this stage). Interpreter + `POST .../runs` planned — see [api.md](api.md#arena) and workspace `visual-programming-system-design v2.md`

### Arena (mock stage)

| Path | Role |
|------|------|
| `app/api/routes/arena.py` | `GET` mission · `GET`/`PUT` attempt |
| `app/schemas/arena.py` | Pydantic DTOs |
| `app/services/arena.py` | In-memory attempt store `(user_id, mission_id) → ast` |
| `app/arena/missions/leo_orbital_launch.py` | M01 pack metadata |
| `tests/test_arena.py` | Auth + save/load round-trip |

No Alembic / DB table yet — process restart clears attempts.

## Deploy (Render — Docker)

Repo นี้มี `Dockerfile` สำหรับ **Render Web Service (Docker)**

| Render setting | ค่า |
|----------------|-----|
| Root directory | `.` (backend repo) |
| Dockerfile path | `Dockerfile` |
| Health check path | `/health` |

**Environment variables** (ตั้งใน Render dashboard):

| Variable | ตัวอย่าง |
|----------|----------|
| `DATABASE_URL` | `postgresql+psycopg://...` จาก Render PostgreSQL |
| `SECRET_KEY` | random string — ห้ามใช้ค่า dev |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | e.g. `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | e.g. `7` |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` |
| `FRONTEND_URL` | URL frontend จริง |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth |
| `GOOGLE_REDIRECT_URI` | `https://<api-host>/auth/google/callback` |
| `AUTH_COOKIE_SECURE` | `true` |

Container รัน `alembic upgrade head` ก่อน start — Dockerfile อ่าน `${PORT:-8000}`

## Git

- Dev บน **`develop`** — ห้าม push ตรงไป **`main`**
- งานใหญ่: `feature/*` จาก `develop` → PR กลับ `develop`
- Release: PR **`develop` → `main`**
- Remote ปัจจุบัน: `Lunar-Backend-2` (แยก repo จาก backend เดิม)

## Boundaries

- ห้าม commit `.env`, Gemini API keys, หรือ RAG index ที่มีข้อมูลลับ
- ห้ามรัน LLM calls จาก frontend
- อย่าเพิ่ม Node.js runtime ใน backend repo
- `GOOGLE_CLIENT_SECRET` ใช้ backend เท่านั้น — ห้ามใส่ใน frontend

## JIT Index

```bash
rg --files -g "*.py" app/
rg "router\\.|APIRouter" app/
rg "google_onetap|verify_google_id_token" app/
rg "GOOGLE_CLIENT" app/core/config.py
```
