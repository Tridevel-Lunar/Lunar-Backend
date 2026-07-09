"""Conversation timing helpers for LAIKA prompts (Asia/Bangkok)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.schemas.laika import ChatMessage

BANGKOK_TZ = ZoneInfo("Asia/Bangkok")
AWAY_THRESHOLD_DAYS = 3


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value or not value.strip():
        return None
    try:
        normalized = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def resolve_now(client_now: str | None) -> datetime:
    parsed = parse_iso_datetime(client_now)
    if parsed is not None:
        return parsed.astimezone(BANGKOK_TZ)
    return datetime.now(BANGKOK_TZ)


def format_datetime_bangkok(dt: datetime) -> str:
    return dt.astimezone(BANGKOK_TZ).strftime("%Y-%m-%d %H:%M")


def format_message_timestamp(created_at: str | None) -> str:
    parsed = parse_iso_datetime(created_at)
    if parsed is None:
        return ""
    return format_datetime_bangkok(parsed)


def latest_message_time(messages: list[ChatMessage]) -> datetime | None:
    latest: datetime | None = None
    for msg in messages:
        parsed = parse_iso_datetime(msg.created_at)
        if parsed is None:
            continue
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def format_conversation_timing_hint(
    messages: list[ChatMessage],
    *,
    client_now: str | None,
) -> str:
    now = resolve_now(client_now)
    latest = latest_message_time(messages)
    if latest is None:
        return (
            "No prior message timestamps. Respond naturally to the current message. "
            "Do not open with a greeting unless the learner greeted first."
        )

    gap = now - latest.astimezone(BANGKOK_TZ)
    days = gap.total_seconds() / 86400
    if days >= AWAY_THRESHOLD_DAYS:
        days_int = max(1, int(round(days)))
        return (
            f"The learner is returning after about {days_int} day(s) away "
            f"(last message {format_datetime_bangkok(latest)}). "
            "Acknowledge their return warmly once in natural mentor Thai, then focus on their question. "
            "Do not repeat greetings in follow-ups."
        )
    if days >= 1:
        return (
            f"Last message was about {int(days)} day(s) ago ({format_datetime_bangkok(latest)}). "
            "A brief warm acknowledgment is optional; otherwise continue directly."
        )

    hours = gap.total_seconds() / 3600
    if hours >= 4:
        return (
            f"Same collection, last message {format_datetime_bangkok(latest)} "
            f"(~{int(hours)} hours ago). Continue naturally without a fresh greeting."
        )

    return (
        "Active or recent conversation. Continue directly — do not open with สวัสดี or welcome-back phrases "
        "unless the learner greeted first."
    )
