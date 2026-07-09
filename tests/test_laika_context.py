from app.core.config import Settings
from app.schemas.laika import AssistRequest, ChatMessage
from app.services.rag.context_window import build_human_prompt, compute_context_usage, trim_messages
from app.services.rag.session_time import format_conversation_timing_hint
from app.services.rag.tokens import resolve_context_window


def test_resolve_context_window_gemma4_e4b() -> None:
    settings = Settings(
        laika_llm_provider="ollama",
        ollama_llm_model="gemma4:e4b",
        laika_context_window=0,
    )
    assert resolve_context_window(settings) == 4096


def test_resolve_context_window_gemma4_e4b_with_num_ctx() -> None:
    settings = Settings(
        laika_llm_provider="ollama",
        ollama_llm_model="gemma4:e4b",
        ollama_num_ctx=8192,
        laika_context_window=0,
    )
    assert resolve_context_window(settings) == 8192


def test_resolve_context_window_gemma3_4b() -> None:
    settings = Settings(
        laika_llm_provider="ollama",
        ollama_llm_model="gemma3:4b",
        laika_context_window=0,
    )
    assert resolve_context_window(settings) == 4096


def test_resolve_context_window_override() -> None:
    settings = Settings(
        laika_llm_provider="ollama",
        ollama_llm_model="gemma3:4b",
        laika_context_window=4096,
    )
    assert resolve_context_window(settings) == 4096


def test_trim_messages_drops_oldest() -> None:
    messages = [
        ChatMessage(role="user", content="a" * 300),
        ChatMessage(role="assistant", content="b" * 300),
        ChatMessage(role="user", content="c" * 300),
    ]
    kept, dropped = trim_messages(messages, max_tokens=220)
    assert dropped >= 1
    assert kept[-1].content.startswith("c")


def test_compute_context_usage_includes_segments() -> None:
    settings = Settings(
        laika_llm_provider="ollama",
        ollama_llm_model="gemma3:4b",
        laika_context_window=8192,
        laika_max_history_tokens=2500,
        laika_reserved_output_tokens=1500,
    )
    usage = compute_context_usage(
        settings,
        intent="explain",
        entry_content="โน้ตทดสอบ",
        current_content="",
        draft="คำถามถัดไป",
        messages=[],
    )
    assert usage.context_window == 8192
    assert usage.input_budget == 8192 - 1500
    assert any(seg.key == "rag" for seg in usage.segments)
    assert any(seg.key == "pending" for seg in usage.segments)


def test_format_history_includes_timestamps() -> None:
    request = AssistRequest.model_validate(
        {
            "entry_type": "note",
            "content": "คำถามใหม่",
            "intent": "explain",
            "client_now": "2026-07-10T10:00:00+07:00",
            "messages": [
                {
                    "role": "user",
                    "content": "สวัสดี",
                    "created_at": "2026-07-05T14:30:00Z",
                },
                {
                    "role": "assistant",
                    "content": "ตอบแล้ว",
                    "created_at": "2026-07-05T14:31:00Z",
                },
            ],
        }
    )
    prompt = build_human_prompt(
        request,
        rag_context="(ctx)",
        history=request.messages,
    )
    assert "Current date/time (Asia/Bangkok): 2026-07-10 10:00" in prompt
    assert "[2026-07-05 21:30] Learner:" in prompt
    assert "Conversation continuity:" in prompt


def test_build_human_prompt_includes_learner_name() -> None:
    request = AssistRequest.model_validate(
        {
            "entry_type": "note",
            "content": "คำถาม",
            "intent": "explain",
            "learner_display_name": "พลอย",
        }
    )
    prompt = build_human_prompt(request, rag_context="(ctx)", history=[])
    assert "Learner name: พลอย" in prompt


def test_resolve_learner_display_name_prefers_display_name() -> None:
    from app.services.rag.learner import resolve_learner_display_name

    assert resolve_learner_display_name("พลอย", "p@example.com") == "พลอย"


def test_resolve_learner_display_name_falls_back_to_email_local() -> None:
    from app.services.rag.learner import resolve_learner_display_name

    assert resolve_learner_display_name(None, "p@example.com") == "p"


def test_timing_hint_welcome_back_after_days() -> None:
    hint = format_conversation_timing_hint(
        [
            ChatMessage(
                role="user",
                content="เดิม",
                created_at="2026-07-01T08:00:00+07:00",
            )
        ],
        client_now="2026-07-10T10:00:00+07:00",
    )
    assert "returning after" in hint
    assert "Do not repeat greetings" in hint or "do not open" in hint.lower()


def test_timing_hint_recent_thread_no_greeting() -> None:
    hint = format_conversation_timing_hint(
        [
            ChatMessage(
                role="user",
                content="เดิม",
                created_at="2026-07-10T09:50:00+07:00",
            )
        ],
        client_now="2026-07-10T10:00:00+07:00",
    )
    assert "Continue directly" in hint
