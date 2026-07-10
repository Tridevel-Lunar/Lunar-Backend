from typing import Literal

from pydantic import BaseModel, Field, field_validator

EntryType = Literal["note", "idea"]
LaikaIntent = Literal[
    "summarize",
    "explain",
    "next-step",
    "analyze",
    "innovation-path",
    "more-ideas",
    "career-path",
]

VALID_INTENTS: frozenset[str] = frozenset(
    {
        "summarize",
        "explain",
        "next-step",
        "analyze",
        "innovation-path",
        "more-ideas",
        "career-path",
    }
)


class LearningContext(BaseModel):
    course: str | None = None
    completed_topics: list[str] = Field(default_factory=list)
    arena_missions: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)
    created_at: str | None = None


class AssistRequest(BaseModel):
    entry_type: EntryType
    content: str = Field(min_length=1, max_length=8000)
    intent: LaikaIntent
    learning_context: LearningContext | None = None
    entry_content: str | None = Field(default=None, max_length=8000)
    messages: list[ChatMessage] = Field(default_factory=list)
    client_now: str | None = None
    learner_display_name: str | None = None
    web_search: bool = False

    @field_validator("messages", mode="before")
    @classmethod
    def drop_empty_messages(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        kept: list[object] = []
        for item in value:
            if isinstance(item, dict):
                content = item.get("content", "")
            else:
                content = getattr(item, "content", "")
            if str(content).strip():
                kept.append(item)
        return kept


class LaikaSource(BaseModel):
    source_id: str
    title: str
    page: int | None = None
    topic: str | None = None
    snippet: str


class AssistResponse(BaseModel):
    response: str
    sources: list[LaikaSource]


class LaikaHealthResponse(BaseModel):
    status: str
    llm_provider: str
    embedding_provider: str
    llm_model: str
    embedding_model: str
    enabled: bool
    context_window: int
    max_history_tokens: int
    reserved_output_tokens: int


class StudioGreetingRequest(BaseModel):
    learning_context: LearningContext | None = None


class StudioGreetingResponse(BaseModel):
    greeting: str


class ContextUsageSegment(BaseModel):
    key: str
    label: str
    tokens: int


class ContextUsageRequest(BaseModel):
    intent: LaikaIntent
    entry_content: str = ""
    current_content: str = ""
    draft: str = ""
    messages: list[ChatMessage] = Field(default_factory=list)
    learning_context: LearningContext | None = None
    web_search: bool = False


class ContextUsageResponse(BaseModel):
    context_window: int
    reserved_output: int
    input_budget: int
    used_input: int
    remaining_input: int
    usage_ratio: float
    segments: list[ContextUsageSegment]
    history_message_count: int
    history_trimmed_count: int
    history_kept_count: int
