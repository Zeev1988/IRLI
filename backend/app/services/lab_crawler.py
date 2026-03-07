"""
Multi-page lab crawler.

Crawls the main lab page, discovers relevant nested links (Publications, Hiring, etc.),
crawls those pages, and combines markdown for extraction.
"""
import asyncio
import logging
import os
from urllib.parse import urljoin, urlparse

from app.config import DEBUG_MODE
from app.services.crawler import (
    _extract_markdown_str,
    crawl_to_result,
    crawl_to_markdown,
)
from app.services.link_extraction import IGNORE_EXTENSIONS, extract_link_candidates

logger = logging.getLogger(__name__)

_MAX_NESTED_PAGES = int(os.getenv("LAB_MAX_NESTED_PAGES", "5"))
_COMBINED_MAX_CHARS = int(os.getenv("LAB_COMBINED_MARKDOWN_MAX_CHARS", "25000"))
_NESTED_CRAWL_DELAY = 0.5

# Link text/URL patterns that indicate content we want (case-insensitive)
_INCLUDE_PATTERNS = (
    "publications",
    "papers",
    "hiring",
    "join",
    "positions",
    "open",
    "vacancies",
    "opportunities",
    "selected works",
    "research",
    "team",
)

# Patterns to exclude (nav, noise)
_EXCLUDE_PATTERNS = (
    "contact",
    "about",
    "news",
    "events",
    "courses",
    "cv",
    "privacy",
    "terms",
    "sitemap",
    "login",
    "search",
)


def _merge_links_from_markdown(links: dict, markdown: str, base_url: str) -> dict:
    """
    Merge CrawlResult.links with links extracted from markdown.
    Crawl4AI sometimes omits links from result.links even when they appear in markdown.
    """
    merged = {
        "internal": list(links.get("internal", []) or []),
        "external": list(links.get("external", []) or []),
    }
    seen = {lnk.get("href") or lnk.get("url", "") for lnk in merged["internal"] + merged["external"]}

    for text, href in extract_link_candidates(markdown, base_url):
        if href in seen:
            continue
        seen.add(href)
        link_data = {"href": href, "text": text}
        # Same institution = internal for our purposes
        if _same_institution(href, base_url):
            merged["internal"].append(link_data)
        else:
            merged["external"].append(link_data)

    return merged


def _get_base_domain(url: str) -> str:
    """Extract base domain (e.g. huji.ac.il) for same-institution comparison."""
    try:
        domain = (urlparse(url).netloc or "").lower().split(":")[0].replace("www.", "")
        if not domain:
            return ""
        parts = domain.split(".")
        # .ac.il, .co.uk, etc. — use last 3 parts
        if len(parts) > 2 and parts[-2] in {"ac", "co", "com", "org", "gov", "edu", "net"}:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])
    except Exception:
        return ""


def _same_institution(url: str, base_url: str) -> bool:
    """Check if url is on same institution (e.g. huji.ac.il) as base_url."""
    base_domain = _get_base_domain(base_url)
    url_domain = _get_base_domain(url)
    return bool(base_domain and url_domain and base_domain == url_domain)


def select_relevant_nested_links(
    links: dict,
    base_url: str,
    max_urls: int = _MAX_NESTED_PAGES,
) -> list[str]:
    """
    Filter links to same-domain or same-institution pages that likely contain
    publications or hiring info. Includes external links from same institution
    (e.g. cs.huji.ac.il from cognitive.huji.ac.il).
    """
    def should_include(text: str, href: str) -> bool:
        text_lower = (text or "").lower().strip()
        resolved = urljoin(base_url, href)
        url_lower = (href or "").lower()
        parsed = urlparse(resolved)
        path = (parsed.path or "").lower()
        fragment = (parsed.fragment or "").lower()
        path_and_fragment = f"{path} {fragment}"

        # Exclude assets
        if any(
            url_lower.endswith(ext) or ext in url_lower.split("?")[0]
            for ext in IGNORE_EXTENSIONS
        ):
            return False

        # Exclude by pattern
        for pat in _EXCLUDE_PATTERNS:
            if pat in text_lower or pat in path:
                return False

        # Include if matches (check path, fragment, and link text)
        for pat in _INCLUDE_PATTERNS:
            if pat in text_lower or pat in path or pat in path_and_fragment:
                return True

        return False

    seen: set[str] = set()
    selected: list[str] = []
    base_normalized = base_url.split("#")[0].rstrip("/")

    def process_link(link: dict) -> bool:
        href = link.get("href") or link.get("url", "")
        text = link.get("text") or link.get("title", "")
        if not href:
            return False
        abs_url = urljoin(base_url, href).split("#")[0].rstrip("/")
        if abs_url in seen:
            return False
        if abs_url == base_normalized:
            return False
        if not should_include(text, href):
            return False
        seen.add(abs_url)
        selected.append(abs_url)
        return len(selected) >= max_urls

    # Internal links (same domain)
    for link in links.get("internal", []) or []:
        if process_link(link):
            return selected

    # External links from same institution (e.g. cs.huji.ac.il from cognitive.huji.ac.il)
    for link in links.get("external", []) or []:
        href = link.get("href") or link.get("url", "")
        if href and not _same_institution(urljoin(base_url, href), base_url):
            continue
        if process_link(link):
            return selected

    return selected


async def crawl_lab_with_nested(url: str) -> str:
    """
    Crawl the main lab page and relevant nested pages, combine markdown.

    In DEBUG_MODE, returns stub markdown and skips nested crawl.
    """
    result = await crawl_to_result(url, page_type="lab")
    main_md = _extract_markdown_str(result)
    combined = [main_md]
    total_chars = len(main_md)

    links = _merge_links_from_markdown(result.links or {}, main_md, url)
    nested_urls = select_relevant_nested_links(links, url)

    for nested_url in nested_urls:
        await asyncio.sleep(_NESTED_CRAWL_DELAY)
        try:
            nested_result = await crawl_to_result(nested_url, page_type="lab")
            nested_md = _extract_markdown_str(nested_result)
            if not nested_md.strip():
                continue

            # Use path as section title
            title = urlparse(nested_url).path.strip("/") or "nested"
            section = f"\n\n## Content from: {title}\n\n{nested_md}"
            combined.append(section)
            total_chars += len(section)

            if total_chars >= _COMBINED_MAX_CHARS:
                break
        except Exception:
            logger.warning("Failed to crawl nested page %s — skipping", nested_url)

    full = "".join(combined)
    if len(full) > _COMBINED_MAX_CHARS:
        full = full[:_COMBINED_MAX_CHARS] + "\n\n[... truncated]"
        logger.info("Combined markdown truncated to %d chars", _COMBINED_MAX_CHARS)

    logger.info(
        "Lab crawl complete: %s — %d nested, %d total chars",
        url,
        len(nested_urls),
        len(full),
    )
    return full
