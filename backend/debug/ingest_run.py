"""
CLI entry point to run the ingestion pipeline manually.

Usage:
    python ingest_run.py                          # ingest all URLs from seeds/faculty_urls.py
    python ingest_run.py https://some-faculty/    # ingest a single faculty index URL
"""
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from app.seeds.faculty_urls import FACULTY_INDEX_URLS
from app.services.ingestion import ingest_faculty


async def main() -> None:
    if len(sys.argv) > 1:
        urls = [sys.argv[1]]
        print(f"Ingesting 1 faculty index: {urls[0]}\n")
    else:
        urls = FACULTY_INDEX_URLS
        print(f"Ingesting {len(urls)} faculty indices from seeds\n")

    for url in urls:
        print(f"--- {url} ---")
        try:
            summary = await ingest_faculty(url)
            print(f"  total={summary['total']} success={summary['success']} failed={summary['failed']}\n")
        except Exception as exc:
            print(f"  ERROR: {exc}\n")
            raise


if __name__ == "__main__":
    asyncio.run(main())
