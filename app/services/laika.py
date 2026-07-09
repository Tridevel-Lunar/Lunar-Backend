from collections.abc import Iterator
from threading import Event

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.laika import AssistRequest, AssistResponse
from app.services.rag.chain import RagChain, StreamEvent
from app.services.rag.context_window import normalize_assist_messages

LaikaStreamEvent = StreamEvent


def run_laika_assist(db: Session, settings: Settings, request: AssistRequest) -> AssistResponse:
    request = normalize_assist_messages(request)
    chain = RagChain(db, settings)
    return chain.run(request)


def stream_laika_assist(
    db: Session,
    settings: Settings,
    request: AssistRequest,
    *,
    cancel_event: Event | None = None,
) -> Iterator[LaikaStreamEvent]:
    request = normalize_assist_messages(request)
    chain = RagChain(db, settings)
    yield from chain.stream(request, cancel_event=cancel_event)
