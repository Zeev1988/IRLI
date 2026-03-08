"""
Crawl a URL and return its content as clean Markdown.

Uses Crawl4AI's AsyncWebCrawler which renders JavaScript, removes boilerplate,
and outputs Markdown — dramatically cutting token noise before the LLM sees it.

Page-type-aware configs:
  - index: Faculty/department list pages — longer delay + full-page scan for dynamic content
  - lab: Individual lab/profile pages — lighter config

Set DEBUG_MODE=true to skip the actual crawl and return stub Markdown instead.
"""
from __future__ import annotations

import os
import logging
from typing import Literal

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, CrawlResult
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import DEBUG_MODE

logger = logging.getLogger(__name__)

_CACHE_ENABLED = os.getenv("CRAWL_CACHE_ENABLED", "true").lower() == "true"
_CACHE_MODE = CacheMode.ENABLED if _CACHE_ENABLED else CacheMode.BYPASS

# Identify crawler for robots.txt compliance; admins can contact via CRAWL_CONTACT_EMAIL
if os.getenv("CRAWL_USER_AGENT"):
    _CRAWL_USER_AGENT = os.getenv("CRAWL_USER_AGENT")
else:
    _contact = f"mailto:{os.getenv('CRAWL_CONTACT_EMAIL')}" if os.getenv("CRAWL_CONTACT_EMAIL") else "contact via project README"
    _CRAWL_USER_AGENT = f"IRLI/1.0 (Israel Research Lab Index; +https://github.com; {_contact})"

_BROWSER_CFG = BrowserConfig(
    headless=True,
    verbose=False,
    user_agent=_CRAWL_USER_AGENT,
)

_BASE_KW = dict(
    cache_mode=_CACHE_MODE,
    word_count_threshold=5,
    remove_overlay_elements=True,
    exclude_external_links=False,  # Keep cross-subdomain links (e.g. cs.huji.ac.il from cognitive.huji.ac.il)
    exclude_social_media_links=True,
    check_robots_txt=True,
)

# Index pages: faculty lists loaded dynamically — wait longer, scroll to trigger lazy load
_INDEX_CFG = CrawlerRunConfig(
    **_BASE_KW,
    delay_before_return_html=4.0,
    scan_full_page=True,
    scroll_delay=0.5,
    max_scroll_steps=15,
)

# Lab pages: individual profiles — lighter config
_LAB_CFG = CrawlerRunConfig(
    cache_mode=_CACHE_MODE,
    word_count_threshold=0,           # IMPORTANT: Don't skip short blocks
    remove_overlay_elements=True,
    exclude_external_links=False,     # Keep this False
    process_iframes=True,             # Some uni sites wrap personal links in iframes
    delay_before_return_html=4.0,
    scan_full_page=True,
    max_scroll_steps=5,
)


def _extract_markdown_str(result: CrawlResult) -> str:
    """Extract markdown string from CrawlResult, handling MarkdownGenerationResult."""
    md = result.markdown
    if md is None:
        return ""
    if hasattr(md, "raw_markdown"):
        return getattr(md, "raw_markdown", "") or ""
    return str(md) if md else ""


async def _do_crawl(url: str, config: CrawlerRunConfig) -> CrawlResult:
    """Single crawl attempt. Raises RuntimeError on failure."""
    async with AsyncWebCrawler(config=_BROWSER_CFG) as crawler:
        result = await crawler.arun(url=url, config=config)

    if not result.success:
        raise RuntimeError(
            f"Crawl failed for {url}: {result.error_message or 'unknown error'}"
        )

    markdown = _extract_markdown_str(result)
    if not markdown.strip():
        raise RuntimeError(f"No readable content extracted from {url}")
    return result


async def crawl_to_result(
    url: str,
    page_type: Literal["index", "lab"] = "lab",
) -> CrawlResult:
    """
    Fetch *url* and return the full CrawlResult (markdown, links, etc.).

    Retries up to 3 times with exponential backoff (4s, 8s, 16s) for flaky university sites.
    In DEBUG_MODE, raises RuntimeError (caller should use crawl_to_markdown stub path).
    """
    config = _INDEX_CFG if page_type == "index" else _LAB_CFG
    logger.info("Crawling %s (page_type=%s)", url, page_type)

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type((RuntimeError, Exception)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        reraise=True,
    ):
        with attempt:
            result = await _do_crawl(url, config)
            logger.info("Crawled %s — %d characters of Markdown", url, len(_extract_markdown_str(result)))
            return result


async def crawl_to_markdown(
    url: str,
    page_type: Literal["index", "lab"] = "lab",
) -> str:
    """
    Fetch *url*, render JavaScript, and return the page as clean Markdown.

    page_type:
      - "index": Faculty/department list page (longer wait, full scan)
      - "lab": Individual lab/profile page (lighter config)

    In DEBUG_MODE, skips the real crawl and returns stub Markdown so the
    full pipeline can be exercised without a browser or network access.

    Raises
    ------
    RuntimeError
        If the crawl fails or returns no usable content.
    """
    result = await crawl_to_result(url, page_type)
    return _extract_markdown_str(result)
