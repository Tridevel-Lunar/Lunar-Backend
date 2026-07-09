"""Learner identity helpers for LAIKA prompts."""


def resolve_learner_display_name(
    display_name: str | None,
    email: str,
) -> str:
    name = (display_name or "").strip()
    if name:
        return name
    local = email.split("@", 1)[0].strip()
    return local or "ผู้เรียน"


def format_learner_identity(learner_display_name: str | None) -> str:
    name = (learner_display_name or "").strip() or "ผู้เรียน"
    return f"Learner name: {name}"
