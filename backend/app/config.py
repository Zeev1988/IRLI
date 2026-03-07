"""
Centralized configuration.

DEBUG_MODE: When true, skip external API calls (LLM, Semantic Scholar, crawl)
and use stubs so the pipeline can run without API keys.
"""
import os

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
