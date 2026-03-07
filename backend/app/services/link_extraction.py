"""
Link extraction and rule-based pre-filtering for faculty index pages.

Extracts all links from markdown, then applies heuristics to drop obvious
non-lab links (nav, footer, assets, social) before sending the remainder
to the LLM for classification.
"""
import re
from urllib.parse import urljoin, urlparse

logger = __import__("logging").getLogger(__name__)

# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^\)]+)\)")
_BARE_URL_RE = re.compile(r"https?://[^\s\)\]\<\>]+")

# File extensions to drop (assets, docs) — exported for lab_crawler
IGNORE_EXTENSIONS = frozenset(
    ".jpg .jpeg .png .gif .svg .webp .ico .css .js .pdf .zip .xml .rss"
    .split()
)

# Link text patterns that indicate nav/footer (case-insensitive)
_IGNORE_TEXT_PATTERNS = (
    "contact", "privacy", "terms", "sitemap", "about us", "about",
    "news", "events", "academics", "admissions", "home",
    "skip to", "back to top", "login", "sign in", "search",
    "facebook", "twitter", "linkedin", "youtube", "instagram",
    "accessibility", "copyright", "follow us", "subscribe",
)

# URL path segments that usually indicate non-lab pages
_IGNORE_PATH_SEGMENTS = (
    "contact", "about", "news", "events", "privacy", "terms",
    "admissions", "courses", "login", "search", "sitemap",
    "facebook.com", "twitter.com", "linkedin.com", "youtube.com",
    "instagram.com", "wikipedia.org",
)


def extract_link_candidates(markdown: str, base_url: str) -> list[tuple[str, str]]:
    """
    Extract all link candidates from markdown.

    Returns [(link_text, absolute_url), ...] deduplicated by URL.
    Skips mailto:, tel:, and anchor-only (#) links.
    """
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []

    def _add(text: str, href: str) -> None:
        href = href.strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            return
        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            return
        if abs_url in seen:
            return
        seen.add(abs_url)
        candidates.append((text.strip() or abs_url, abs_url))

    for text, href in _MD_LINK_RE.findall(markdown):
        _add(text, href)

    for match in _BARE_URL_RE.finditer(markdown):
        url = match.group(0)
        if url not in seen:
            seen.add(url)
            candidates.append((url, url))

    return candidates


def prefilter_lab_candidates(
    candidates: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """
    Rule-based pre-filter to drop obvious non-lab links before LLM classification.

    Removes: assets (.jpg, .css, etc.), nav/footer text patterns, social domains,
    and common non-lab path segments.
    """
    filtered: list[tuple[str, str]] = []
    for text, url in candidates:
        if _is_obvious_non_lab(text, url):
            continue
        filtered.append((text, url))
    if len(filtered) < len(candidates):
        logger.debug(
            "Prefilter: %d -> %d candidates (dropped %d)",
            len(candidates), len(filtered), len(candidates) - len(filtered),
        )
    return filtered


def _is_obvious_non_lab(text: str, url: str) -> bool:
    """Return True if this link is obviously not a lab/researcher page."""
    text_lower = text.lower().strip()
    url_lower = url.lower()

    # Asset / document URLs
    if any(url_lower.endswith(ext) or ext in url_lower.split("?")[0] for ext in IGNORE_EXTENSIONS):
        return True

    # Empty or very short link text with generic URL
    if len(text_lower) <= 2 and ("/" in url_lower or "?" in url_lower):
        return True

    # Nav/footer link text
    for pattern in _IGNORE_TEXT_PATTERNS:
        if pattern in text_lower:
            return True

    # Non-lab path segments or domains
    parsed = urlparse(url_lower)
    path_and_netloc = (parsed.path or "") + " " + (parsed.netloc or "")
    for segment in _IGNORE_PATH_SEGMENTS:
        if segment in path_and_netloc:
            return True

    return False
