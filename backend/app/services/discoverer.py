"""
Link-discovery service.

Given a faculty/department index URL, crawls the page and uses the LLM to
identify all URLs that point to individual researcher or lab pages.

Uses link_extraction for extraction and rule-based pre-filtering, then sends
the remaining (text, url) pairs to the LLM for classification.
"""
import logging
from typing import Annotated

from pydantic import BaseModel, HttpUrl, Field

from app.config import DEBUG_MODE
from app.services.crawler import crawl_to_markdown
from app.services.link_extraction import extract_link_candidates, prefilter_lab_candidates
from app.services.llm_client import get_client_and_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response schema for the discovery LLM call
# ---------------------------------------------------------------------------
class LabLinks(BaseModel):
    urls: Annotated[
        list[HttpUrl],
        Field(description="All URLs linking to individual researcher or lab pages"),
    ]


_SYSTEM_PROMPT = (
    "You are a web-scraping assistant. Given a list of link candidates from a "
    "university faculty or department index page (format: \"link text\" -> URL), "
    "return ONLY the URLs that point to individual researcher personal pages, "
    "lab pages, or faculty profiles. Exclude links to courses, admin pages, "
    "news articles, navigation (About, Contact, etc.), and external sites."
)


def _format_candidates(candidates: list[tuple[str, str]]) -> str:
    return "\n".join(f'"{text}" -> {url}' for text, url in candidates)


async def discover_lab_urls(index_url: str) -> list[str]:
    """
    Crawl *index_url* and return a deduplicated list of individual lab/researcher URLs.

    In DEBUG_MODE returns a small hardcoded list without making any network calls.
    """
    logger.info("Discovering lab URLs on %s", index_url)
    markdown = await crawl_to_markdown(index_url, page_type="index")

    candidates = extract_link_candidates(markdown, index_url)
    logger.info("Extracted %d link candidates from %s", len(candidates), index_url)

    candidates = prefilter_lab_candidates(candidates)
    if not candidates:
        logger.warning("No link candidates found on %s", index_url)
        return []

    client, model = get_client_and_model()

    payload = (
        f"Faculty index URL: {index_url}\n\n"
        f"--- LINK CANDIDATES ---\n{_format_candidates(candidates)}\n--- END ---"
    )

    result: LabLinks = await client.chat.completions.create(
        model=model,
        response_model=LabLinks,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": payload},
        ],
        max_retries=2,
    )

    urls = [str(u) for u in result.urls]
    unique_urls = list(dict.fromkeys(urls))  # deduplicate preserving order
    logger.info("Discovered %d lab URLs on %s", len(unique_urls), index_url)
    return unique_urls
