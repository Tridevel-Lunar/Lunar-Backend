"""LangChain tool definitions for LAIKA's agentic tool-calling loop.

Tools:
- ``search_knowledge`` — pgvector similarity search over LUNAR's engineering corpus.
- ``search_web`` — DuckDuckGo web search for current / external information.
"""

from langchain_core.tools import tool

from app.schemas.laika import LaikaSource
from app.services.rag.prompts import format_context
from app.services.rag.retriever import PgVectorRetriever
from app.services.rag.sources import build_sources
from app.services.rag.web_search import (
    format_web_results,
    search_web as search_web_ddg,
    web_results_to_sources,
)

MAX_TOOL_ROUNDS = 3


def make_knowledge_tool(retriever: PgVectorRetriever):
    """Return a ``search_knowledge`` tool bound to the given retriever."""

    @tool
    def search_knowledge(query: str) -> str:
        """Search the LUNAR knowledge base (CubeSat, space, physics docs).
        Use for technical concepts, orbital mechanics, power budgets,
        embedded systems — anything from Space/Arena lessons.
        """
        chunks = retriever.retrieve(query)
        return format_context(chunks)

    return search_knowledge


def make_web_tool():
    """Return a ``search_web`` tool."""

    @tool
    def search_web(query: str) -> str:
        """Search the internet for current or external information.
        Use for recent news, pricing, real-world missions, career info,
        or anything outside the static LUNAR knowledge base.
        """
        results = search_web_ddg(query, max_results=3)
        return format_web_results(results)

    return search_web


def execute_tool_call(
    tool_call: dict,
    retriever: PgVectorRetriever,
) -> tuple[str, list[LaikaSource]]:
    """Execute a single tool call and return (result_text, sources)."""
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    if name == "search_knowledge":
        query = args.get("query", "")
        chunks = retriever.retrieve(query)
        return format_context(chunks), build_sources(chunks)

    if name == "search_web":
        query = args.get("query", "")
        results = search_web_ddg(query, max_results=3)
        sources = web_results_to_sources(results)
        return format_web_results(results), sources

    return f"Unknown tool: {name}", []


def tool_name_to_status(name: str) -> str:
    """Map a tool name to a LaikaStatusPhase string."""
    if name == "search_knowledge":
        return "tool_searching"
    if name == "search_web":
        return "tool_searching_web"
    return "tool_searching"
