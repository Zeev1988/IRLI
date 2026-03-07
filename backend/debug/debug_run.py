"""
CLI debug entry point — runs the full crawl → extract pipeline without
starting the FastAPI server.

Usage:
    python debug_run.py                          # uses DEBUG_MODE stub
    python debug_run.py https://some-lab-url/    # crawls a real URL (needs API key)

Set DEBUG_MODE=true in .env (or export it) to skip crawl + LLM entirely.
"""
import asyncio
import json
import sys

from dotenv import load_dotenv

from app.services.lab_crawler import crawl_lab_with_nested

load_dotenv()

from app.services.crawler import crawl_to_markdown
from app.services.extractor import extract_lab_data, DEBUG_MODE


async def main(url: str) -> None:
    print(f"\n{'='*60}")
    print(f"  IRLI Debug Runner")
    print(f"  URL        : {url}")
    print(f"  DEBUG_MODE : {DEBUG_MODE}")
    print(f"{'='*60}\n")

    print("[ 1 / 2 ] Crawling...")
    markdown = await crawl_lab_with_nested(url)
    print(f"          → {len(markdown)} chars of Markdown\n")
    print("--- Markdown preview (first 500 chars) ---")
    print(markdown[:500])
    print("------------------------------------------\n")

    print("[ 2 / 2 ] Extracting LabProfile...")
    profile = await extract_lab_data(markdown, url)
    print("\n--- LabProfile ---")
    print(json.dumps(profile.model_dump(mode="json"), indent=2, ensure_ascii=False))
    print("------------------\n")


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com/stub"
    asyncio.run(main(target_url))
