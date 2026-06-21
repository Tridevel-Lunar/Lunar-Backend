# LUNAR Backend

Python **FastAPI** — API server เชื่อม frontend กับสคริปต์ฟิสิกส์, simulation, และ LAIKA

**Product context:** [../../frontend/docs/concept.md](../../frontend/docs/concept.md) · [functional-spec](../../frontend/docs/functional-spec.md)  
**Docker dev:** [../../docs/docker-dev.md](../../docs/docker-dev.md) (compose อยู่ที่ workspace root)

## บทบาทหลัก

| หน้าที่ | รายละเอียด |
|---------|------------|
| **API Gateway** | รับ request จาก frontend — รันบล็อกโค้ด, ส่งผล simulation กลับ |
| **Orbital / Physics** | คำนวณสมการฟิสิกส์อวกาศ, วงโคจร, power budget |
| **Logging** | โครงสร้างข้อมูล log จากการจำลอง |
| **LAIKA** | LLM (Gemini) + RAG ให้คำแนะนำผู้เรียน |
| **Satellite imagery** | ส่งข้อมูลภาพดาวเทียมกลับ frontend (เมื่อมี) |

## Tech Stack

### ภาษา

| ภาษา | การใช้งาน |
|------|-----------|
| **Python** | ภาษาหลัก — สมการฟิสิกส์อวกาศ, วงโคจร, โครงสร้างข้อมูล log |

### Framework & Libraries

| เครื่องมือ | บทบาท |
|-----------|--------|
| **FastAPI** | API server / gateway |
| **PostgreSQL** | ฐานข้อมูลหลัก — users, portfolios, simulation logs, ฯลฯ |
| **SQLAlchemy** + **Alembic** | ORM + migrations (เมื่อ implement) |
| **Poliastro** | คำนวณและจำลองวงโคจรดาวเทียม (orbital mechanics, Kepler) |
| **PyEphem** | ทางเลือก/เสริม — ตำแหน่งดาราศาสตร์, ephemeris |
| **Gemini API** (Google AI SDK) | LLM หลักของ LAIKA — วิเคราะห์ไอเดีย, สร้างกล่องคำพูดแนะนำ |
| **LangChain** หรือ **LlamaIndex** | RAG — ดึงฐานความรู้ (เช่น NASA CubeSat 101 PDF) มาอ้างอิงก่อนตอบ |

> ไม่ใช้ Node.js/Express — backend เป็น Python + FastAPI เท่านั้น

### AI (LAIKA)

```
ผู้เรียน → Frontend → FastAPI → [RAG: LangChain/LlamaIndex] → Gemini API → คำตอบ
                                      ↑
                              NASA docs, CubeSat 101, ฯลฯ
```

- RAG ลด hallucination — ตอบจากเอกสารวิศวกรรมอวกาศจริง
- API keys อยู่ใน `.env` เท่านั้น — ห้าม commit

### Database

- **PostgreSQL** — ต่อผ่าน `DATABASE_URL` ใน `backend/.env`
- Dev (Docker): `postgresql://lunar:lunar@postgres:5432/lunar` (compose ตั้งให้)
- Dev (backend local): `postgresql://lunar:lunar@localhost:5432/lunar`
- Migrations: **Alembic** — `alembic upgrade head` (Docker entrypoint runs this on start)

## โครงสร้างปัจจุบัน

```
backend/
├── alembic/
├── app/
│   ├── api/routes/auth.py
│   ├── core/config.py, security.py
│   ├── db/session.py
│   ├── models/user.py
│   ├── schemas/auth.py
│   ├── services/auth.py
│   └── main.py
├── docs/api.md
├── pytest.ini
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_health.py
│   └── test_security.py
├── requirements.txt
└── .env.example
```

Dev Dockerfile อยู่ที่ workspace [`docker/backend.Dockerfile.dev`](../../docker/backend.Dockerfile.dev) — ดู [docker-dev.md](../../docs/docker-dev.md)

## Commands

```bash
# Docker (จาก Lunar/)
docker compose up --build backend

# Local
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Tests
pytest
```

**Default API URL:** `http://localhost:8000`  
Frontend เรียกผ่าน `NEXT_PUBLIC_API_URL` (หรือ equivalent) ใน `.env` ของ frontend

## API

- **Swagger UI:** http://localhost:8000/docs
- Contract summary: [docs/api.md](docs/api.md)

## Testing

Backend ใช้ **pytest** + FastAPI `TestClient` — ไม่ต้องรัน Postgres/Docker สำหรับ unit/API tests (ใช้ SQLite in-memory)

### รันเทส

```bash
cd backend
pip install -r requirements.txt
pytest              # ทั้งหมด
pytest -v           # verbose
pytest tests/test_auth.py   # ไฟล์เดียว
```

จาก workspace root (backend container ยังรันอยู่):

```bash
docker compose exec backend pytest
```

### โครงสร้าง

| ไฟล์ | ครอบคลุม |
|------|-----------|
| `tests/conftest.py` | SQLite in-memory DB, `client` fixture, `auth_headers` |
| `tests/test_health.py` | `GET /health` |
| `tests/test_security.py` | password hash/verify, JWT create/decode |
| `tests/test_auth.py` | register, login, `/auth/me`, 409 duplicate, 401 invalid, Google 503 |

### หมายเหตุ

- เทส override `get_db` — ไม่แตะ PostgreSQL จริง
- env ในเทส: `SECRET_KEY`, `GOOGLE_CLIENT_*` ว่าง (OAuth disabled)
- เพิ่ม endpoint ใหม่ → เพิ่มเทสใน `tests/` ก่อน merge PR

### Manual / E2E (optional)

หลัง `docker compose up`:

1. Swagger: http://localhost:8000/docs — register → Authorize → `/auth/me`
2. Frontend: http://localhost:3000/register → dashboard → logout

## Code Style

- Python 3.11+
- Type hints บน function signatures
- Async endpoints เมื่อเหมาะสม
- Comments และ docstrings ภาษา**อังกฤษ**
- ชื่อ product: **LAIKA**, **Space**, **Arena**, **Studio**

## Frontend ↔ Backend

- ไม่ import ข้าม repo — HTTP เท่านั้น
- ฟิสิกส์/วงโคจรรันฝั่ง backend; frontend แสดงผล
- Blockly block definitions อาจ share เป็น JSON schema ผ่าน API ไม่ใช่ shared package

## Deploy (Render — Docker)

Repo นี้มี `Dockerfile` สำหรับ **Render Web Service (Docker)** — โครงสร้างคล้าย dev image ใน workspace (`docker/backend.Dockerfile.dev`) แต่ไม่มี `--reload`

| Render setting | ค่า |
|----------------|-----|
| Root directory | `.` (backend repo) |
| Dockerfile path | `Dockerfile` |
| Health check path | `/health` |

**Environment variables** (ตั้งใน Render dashboard):

| Variable | ตัวอย่าง |
|----------|----------|
| `DATABASE_URL` | `postgresql+psycopg://...` จาก Render PostgreSQL (Internal URL) |
| `SECRET_KEY` | random string — ห้ามใช้ค่า dev |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` |
| `FRONTEND_URL` | URL frontend จริง (OAuth redirect กลับ) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | ถ้าเปิด Google OAuth |
| `GOOGLE_REDIRECT_URI` | `https://<api-host>/auth/google/callback` |

Container รัน `alembic upgrade head` ก่อน start ทุกครั้ง — ไม่ต้อง migrate แยก manual  
Render ตั้ง `PORT` ให้อัตโนมัติ — Dockerfile อ่าน `${PORT:-8000}`

## Git

- Dev บน **`develop`** — ห้าม push ตรงไป **`main`**
- งานใหญ่: `feature/*` จาก `develop` → PR กลับ `develop`
- Release: PR **`develop` → `main`**
- ถ้ายังไม่มี `develop`: สร้างจาก `main` แล้ว push ครั้งเดียว (ดู [../../docs/git-workflow.md](../../docs/git-workflow.md))

## Boundaries

- ห้าม commit `.env`, Gemini API keys, หรือ RAG index ที่มีข้อมูลลับ
- ห้ามรัน LLM calls จาก frontend
- อย่าเพิ่ม Node.js runtime ใน backend repo

## JIT Index

```bash
# (เมื่อมี code)
rg --files -g "*.py" app/
rg "router\\.|APIRouter" app/
```
