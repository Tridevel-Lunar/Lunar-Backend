from typing import Literal

LaikaStatusPhase = Literal["embedding", "searching", "searching_web", "generating"]

LAIKA_STATUS_MESSAGES: dict[LaikaStatusPhase, str] = {
    "embedding": "กำลังวิเคราะห์คำถาม…",
    "searching": "กำลังค้นหาเอกสารอ้างอิง…",
    "searching_web": "กำลังค้นหาข้อมูลจากอินเทอร์เน็ต…",
    "generating": "กำลังสร้างคำตอบ…",
}


def laika_status_message(phase: LaikaStatusPhase) -> str:
    return LAIKA_STATUS_MESSAGES[phase]
