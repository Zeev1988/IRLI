"""
CLI entry point to run the metrics enrichment pipeline manually.

Usage:
    python enrich_run.py                    # enrich all labs in DB
    python enrich_run.py 10                 # enrich first 10 labs
    python enrich_run.py --lab 42           # enrich single lab by ID
    python enrich_run.py --stub              # enrich extractor DEBUG_STUB profiles and upsert to Supabase
    python enrich_run.py --template         # use template (no DB, no API)
    python enrich_run.py --fetch             # test S2 API: search + fetch (template profile)
    python enrich_run.py --fetch-id [id]     # test fetch_author_metrics (omit id for default)

Set DEBUG_MODE=true in .env to skip Semantic Scholar API and use stub values.
With --template, skips DB and API entirely; uses a hardcoded LabProfile example.
"""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from app.config import DEBUG_MODE
from app.db.database import AsyncSessionLocal
from app.services.ingestion import upsert_profile
from app.services.metrics_enricher import (
    enrich_all_labs,
    enrich_lab_metrics,
    fetch_author_metrics,
    search_and_fetch_metrics,
)
from debug.stubs import DEBUG_STUB

# Default author ID for --fetch-id (Geoffrey Hinton, well-known researcher)
DEFAULT_TEST_AUTHOR_ID = "114131011"

# Template LabProfile for DEBUG_MODE + --template (no DB required)
TEMPLATE_PROFILE = {
    "pi_name": "Omri Abend",
    "institution": "The Hebrew University of Jerusalem",
    "faculty": "Computer Science and Engineering; Cognitive and Brain Sciences",
    "research_summary": [
        "Developing manual and computational methods for mapping text to structured semantic and grammatical representations",
        "Modeling the computational mechanisms of child language acquisition and word categorization",
        "Advancing language technologies including neural machine translation, information extraction, and LLM evaluation",
    ],
    "keywords": [
        "NLP",
        "Computational Linguistics",
        "Semantic Parsing",
        "Machine Translation",
        "Language Acquisition",
    ],
    "technologies": [
        "Large Language Models",
        "Natural Language Processing",
        "Computational Linguistics",
        "Semantic Parsing",
        "Reinforcement Learning",
        "Machine Translation",
        "Information Extraction",
        "Cognitive Modeling",
        "Lexical Alignment",
        "Text Simplification",
        "Image Captioning",
        "Theory of Mind",
        "Universal Conceptual Cognitive Annotation",
    ],
    "hiring_status": "Not mentioned",
    "lab_url": "https://www.cs.huji.ac.il/~oabend/",
}


async def __run_fetch_mode() -> None:
    """Test Semantic Scholar API: search + fetch using template profile."""
    print(f"\n{'='*60}")
    print("  IRLI Metrics Enrichment — Semantic Scholar API Test")
    print(f"  DEBUG_MODE : {DEBUG_MODE}")
    print(f"{'='*60}\n")
    pi_name = TEMPLATE_PROFILE["pi_name"]
    institution = TEMPLATE_PROFILE["institution"]
    print(f"Search: \"{pi_name}\" (filter by institution: {institution})")
    print("Fetching metrics...")
    metrics = await search_and_fetch_metrics(pi_name, institution)
    if metrics:
        print(f"\n  publication_count : {metrics.get('paperCount')}")
        print(f"  citation_count   : {metrics.get('citationCount')}")
        print(f"  hIndex            : {metrics.get('hIndex')}")
        print("\n→ Fetch OK\n")
    else:
        print("\n→ Fetch FAILED (no match or API error)\n")


async def __run_fetch_id_mode(author_id: str) -> None:
    """Test _fetch_author_metrics directly with a Semantic Scholar author ID."""
    print(f"\n{'='*60}")
    print("  IRLI Metrics — fetch_author_metrics Test")
    print(f"  author_id : {author_id}")
    print(f"{'='*60}\n")
    metrics = await fetch_author_metrics(author_id)
    if metrics:
        print(f"  publication_count : {metrics.get('paperCount')}")
        print(f"  citation_count   : {metrics.get('citationCount')}")
        print(f"  hIndex            : {metrics.get('hIndex')}")
        print("\n→ Fetch OK\n")
    else:
        print("→ Fetch FAILED\n")


async def __run_stub_mode() -> None:
    """Enrich extractor DEBUG_STUB profiles and upsert to Supabase."""
    print(f"\n{'='*60}")
    print("  IRLI — Enrich & Upsert DEBUG_STUB Profiles")
    print(f"  DEBUG_MODE : {DEBUG_MODE}")
    print(f"{'='*60}\n")

    success = 0
    for profile in DEBUG_STUB:
        print(f"Enriching: {profile.pi_name} ({profile.lab_url})...")
        metrics = None if DEBUG_MODE else await search_and_fetch_metrics(
            profile.pi_name,
            profile.institution,
            representative_papers=profile.representative_papers or None,
        )
        await upsert_profile(profile, metrics=metrics, generate_embedding=not DEBUG_MODE)
        print(f"  → papers={metrics.get('paperCount')}, citations={metrics.get('citationCount')}, h={metrics.get('hIndex')}")
        success += 1

    print(f"\nUpserted {success}/{len(DEBUG_STUB)} profiles.\n")


def __run_template_mode() -> None:
    """Run enrichment with template profile — no DB, no API."""
    print(f"\n{'='*60}")
    print("  IRLI Metrics Enrichment Runner (template mode)")
    print("  SKIP: DB, Semantic Scholar API")
    print(f"{'='*60}\n")
    print("Template LabProfile:")
    print(json.dumps(TEMPLATE_PROFILE, indent=2, ensure_ascii=False))
    print()
    query = f"{TEMPLATE_PROFILE['pi_name']} {TEMPLATE_PROFILE['institution']}"
    print(f"Would search Semantic Scholar: query=\"{query}\"")
    print("Stub metrics (DEBUG_MODE): publication_count=0, citation_count=0, h_index=0")
    print("\n→ Template mode complete (no DB write)\n")


async def main() -> None:
    print(f"\n{'='*60}")
    print("  IRLI Metrics Enrichment Runner")
    print(f"  DEBUG_MODE : {DEBUG_MODE}")
    print(f"{'='*60}\n")

    if "--lab" in sys.argv:
        idx = sys.argv.index("--lab")
        if idx + 1 >= len(sys.argv):
            print("Usage: python enrich_run.py --lab <lab_id>")
            sys.exit(1)
        lab_id = int(sys.argv[idx + 1])
        print(f"Enriching single lab ID={lab_id}...")
        async with AsyncSessionLocal() as session:
            ok = await enrich_lab_metrics(lab_id, session)
        print(f"  → {'OK' if ok else 'FAILED'}\n")
        return

    args = [a for a in sys.argv[1:] if a != "--only-without-metrics"]
    only_without = "--only-without-metrics" in sys.argv
    limit = int(args[0]) if args and args[0].isdigit() else None
    if limit:
        print(f"Enriching up to {limit} labs...\n")
    else:
        print("Enriching all labs...\n")
    if only_without:
        print("(only labs without metrics)\n")

    result = await enrich_all_labs(limit=limit, only_without_metrics=only_without)
    print(f"  total  : {result['total']}")
    print(f"  success: {result['success']}")
    print(f"  failed : {result['failed']}\n")


if __name__ == "__main__":
    if "--stub" in sys.argv:
        asyncio.run(__run_stub_mode())
        sys.exit(0)
    if "--template" in sys.argv:
        __run_template_mode()
        sys.exit(0)
    if "--fetch" in sys.argv:
        asyncio.run(__run_fetch_mode())
        sys.exit(0)
    if "--fetch-id" in sys.argv:
        idx = sys.argv.index("--fetch-id")
        author_id = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else DEFAULT_TEST_AUTHOR_ID
        asyncio.run(__run_fetch_id_mode(author_id))
        sys.exit(0)
    asyncio.run(main())
