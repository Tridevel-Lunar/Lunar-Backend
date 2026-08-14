from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.schemas.laika import LearningContext, StudioGreetingResponse
from app.services.rag.chain import _chunk_text
from app.services.rag.prompts import get_studio_greeting_prompt, format_learning_context
from app.services.rag.providers import get_llm


def run_studio_greeting(
    settings: Settings,
    learning_context: LearningContext | None = None,
) -> StudioGreetingResponse:
    ctx = learning_context.model_dump() if learning_context else None
    progress = format_learning_context(ctx)

    messages = [
        SystemMessage(content=get_studio_greeting_prompt()),
        HumanMessage(content=f"Learner progress:\n{progress}"),
    ]
    response = get_llm(settings).invoke(messages)
    text = _chunk_text(response.content).strip()
    return StudioGreetingResponse(greeting=text)
