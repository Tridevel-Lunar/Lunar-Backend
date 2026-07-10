"""DuckDuckGo web search for LAIKA — prototype web retrieval layer.

Provides a `WebSearchResult` and `search_web()` that fetches top-N results
from DuckDuckGo as plain-text snippets, suitable for inclusion in RAG context.
"""

from dataclasses import dataclass, field

from duckduckgo_search import DDGS

from app.schemas.laika import LaikaSource


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    href: str
    body: str


def search_web(query: str, max_results: int = 3) -> list[WebSearchResult]:
    """Run a DuckDuckGo search and return text results.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 3).

    Returns:
        A list of ``WebSearchResult`` named tuples — empty on error or no results.
    """
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []

    results: list[WebSearchResult] = []
    for item in raw:
        title = item.get("title", "")
        href = item.get("href", "")
        body = item.get("body", "")
        if title or body:
            results.append(WebSearchResult(title=title, href=href, body=body))
    return results


def format_web_results(results: list[WebSearchResult]) -> str:
    """Format web search results into a plain-text context block."""
    if not results:
        return ""
    parts: list[str] = []
    for i, r in enumerate(results, start=1):
        parts.append(f"[Web {i}] {r.title}\n{r.body}\nSource: {r.href}")
    return "\n\n".join(parts)


def web_results_to_sources(results: list[WebSearchResult]) -> list[LaikaSource]:
    """Convert web search results into ``LaikaSource`` entries for frontend references."""
    sources: list[LaikaSource] = []
    seen_urls: set[str] = set()
    for r in results:
        url = r.href.strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        snippet = r.body[:200]
        if len(r.body) > 200:
            snippet += "…"
        sources.append(
            LaikaSource(
                source_id=f"web:{url}",
                title=r.title or url,
                page=None,
                topic="web",
                snippet=snippet,
            )
        )
    return sources
