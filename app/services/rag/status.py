from typing import Literal

LaikaStatusPhase = Literal["embedding", "searching", "generating"]

LAIKA_STATUS_MESSAGES: dict[LaikaStatusPhase, str] = {
    "embedding": "กำลังวิเคราะห์คำถาม…",
    "searching": "กำลังค้นหาเอกสารอ้างอิง…",
    "generating": "กำลังสร้างคำตอบ…",
}


def laika_status_message(phase: LaikaStatusPhase) -> str:
    return LAIKA_STATUS_MESSAGES[phase]
