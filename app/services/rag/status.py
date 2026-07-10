from typing import Literal

LaikaStatusPhase = Literal[
    "embedding",
    "searching",
    "searching_web",
    "reasoning",
    "tool_searching",
    "tool_searching_web",
    "generating",
]

LAIKA_STATUS_MESSAGES: dict[LaikaStatusPhase, str] = {
    "embedding": "กำลังวิเคราะห์คำถาม…",
    "searching": "กำลังค้นหาเอกสารอ้างอิง…",
    "searching_web": "กำลังค้นหาข้อมูลจากอินเทอร์เน็ต…",
    "reasoning": "LAIKA กำลังคิดว่าจะค้นหาอะไรเพิ่ม…",
    "tool_searching": "กำลังค้นหาในคลังความรู้…",
    "tool_searching_web": "กำลังค้นหาจากอินเทอร์เน็ต…",
    "generating": "กำลังสร้างคำตอบ…",
}


def laika_status_message(phase: LaikaStatusPhase) -> str:
    return LAIKA_STATUS_MESSAGES[phase]
