# LUNAR Backend

Python **FastAPI** — API server เชื่อม frontend กับสคริปต์ฟิสิกส์, simulation, และ LAIKA

**Product context:** [../../frontend/docs/concept.md](../../frontend/docs/concept.md)  
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
- Migrations: **Alembic** (เมื่อมี models)

## โครงสร้างปัจจุบัน

```
backend/
├── app/
│   ├── __init__.py
│   └── main.py              # FastAPI entry + /health (ขยายต่อได้)
├── Dockerfile.dev           # dev image — อยู่ใน repo นี้
├── docs/
├── requirements.txt
├── .env.example
└── README.md
```

`compose.dev.yaml` อยู่ที่ **Lunar workspace root** (นอก git ของ FE/BE) — orchestrate ทั้งสอง service ในเครื่อง dev

## Commands

```bash
# Docker (จาก Lunar/)
docker compose -f compose.dev.yaml up --build backend

# Local
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Default API URL:** `http://localhost:8000`  
Frontend เรียกผ่าน `NEXT_PUBLIC_API_URL` (หรือ equivalent) ใน `.env` ของ frontend

## API Conventions (วางแผน)

- REST JSON — handlers บาง ส่งต่อ `services/`
- Pydantic v2 สำหรับ request/response schemas
- บันทึก endpoint contract ใน `docs/api.md` เมื่อเริ่ม implement
- CORS อนุญาต frontend origin (`http://localhost:3000` ใน dev)

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
