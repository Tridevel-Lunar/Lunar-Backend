from typing import Literal

from pydantic import BaseModel, Field, model_validator

LaikaMode = Literal["standard", "extra"]

EntryType = Literal["note", "idea", "learn"]
LaikaIntent = Literal[
    "summarize",
    "explain",
    "next-step",
    "analyze",
    "innovation-path",
    "more-ideas",
    "career-path",
    "ask-anything",
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
        "ask-anything",
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
    content: str = Field(min_length=0, max_length=8000)
    intent: LaikaIntent
    learning_context: LearningContext | None = None
    entry_content: str | None = Field(default=None, max_length=8000)
    messages: list[ChatMessage] = Field(default_factory=list)
    client_now: str | None = None
    learner_display_name: str | None = None
    web_search: bool = False
    mode: LaikaMode = "standard"

    @model_validator(mode="before")
    @classmethod
    def drop_empty_messages(cls, data: dict) -> dict:
        raw = data.get("messages")
        if isinstance(raw, list):
            data["messages"] = [
                m for m in raw
                if isinstance(m, dict) and m.get("content", "").strip()
            ]
        return data


class StreamAssistRequest(BaseModel):
    """Lean request for streaming — backend fetches entry_type/entry_content/messages from DB."""
    collection_id: str
    content: str = Field(min_length=0, max_length=8000)
    intent: LaikaIntent
    mode: Literal["new", "follow_up", "edit", "retry", "branch"] = "follow_up"
    node_id: str | None = None
    parent_node_id: str | None = None
    web_search: bool = False
    laika_mode: LaikaMode = "standard"
    learning_context: LearningContext | None = None


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
    mode: LaikaMode = "standard"


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
