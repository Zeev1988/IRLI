"""
LLM-based extraction agent.

Supports two providers, controlled by the LLM_PROVIDER env var:
  - "openai"  → GPT-4o-mini (default)
  - "gemini"  → Gemini 1.5 Flash

Set DEBUG_MODE=true to skip all API calls and return a hardcoded stub,
which lets you run and test the full pipeline without any API keys.
"""
import logging
import textwrap

from app.config import DEBUG_MODE
from app.models.lab import LabProfile
from app.services.llm_client import get_client_and_model, get_provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a research-lab data extractor. Given the Markdown content of a
    university faculty or research-lab web page, extract the following
    information and return it as structured JSON matching the schema exactly.

    The content may come from multiple pages (main lab page plus nested pages
    such as Publications, Hiring, Join Us). Extract from all sections. If the
    same field appears in multiple places, prefer the most specific or recent.

    Rules:
    - pi_name: Full name of the Principal Investigator (professor/researcher).
    - institution: Official university name.
    - faculty: Department or faculty (e.g. "Computer Science", "Brain Sciences").
    - research_summary: 2 to 5 concise bullet points (plain strings, no dashes).
    - keywords: 3 to 8 short technical tags (e.g. "fMRI", "NLP", "CRISPR").
    - technologies: 0 to 15 research domains, buzz words, and searchable topics.
      Include methodologies, techniques, and broad themes (e.g. Large Language Models,
      fMRI, Reinforcement Learning, Semantic Parsing, psychedelics, CRISPR, RNA-seq).
      Do NOT include specific software, languages, or packages (Python, PyTorch, R, etc.).
      Goal: help users find labs by topic (e.g. "LLM", "MRI", "psychedelics").
    - hiring_status: true if they explicitly mention looking for students/postdocs,
      false if explicitly not hiring, or a short quoted string if ambiguous
      (e.g. "Not mentioned").
    - lab_url: The canonical URL of this specific lab page (use the provided URL
      if no dedicated lab URL is found on the page).
    - representative_papers: 0 to 5 paper titles when listed on the page (e.g. under
      Publications, Selected Works, Key Papers, Recent Papers). Use exact titles as shown.
      Leave empty if no papers are listed. These help disambiguate the PI in author databases.

    If a field cannot be determined from the content, use a reasonable placeholder
    (e.g. empty string or false) rather than omitting the field.
""")


def _user_prompt(markdown: str, url: str) -> str:
    trimmed = markdown[:12_000]
    return (
        f"Lab page URL: {url}\n\n"
        f"--- PAGE CONTENT (Markdown) ---\n{trimmed}\n--- END ---"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def extract_lab_data(markdown: str, url: str) -> LabProfile:
    """
    Call the configured LLM and return a validated LabProfile.

    In DEBUG_MODE, skips the LLM entirely and returns a hardcoded stub so
    you can test the full endpoint pipeline without any API keys.
    """
    client, model = get_client_and_model()
    logger.info("Extracting lab data via %s (%s)", get_provider(), model)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(markdown, url)},
    ]

    profile: LabProfile = await client.chat.completions.create(
        model=model,
        response_model=LabProfile,
        messages=messages,
        max_retries=3,
    )
    logger.info("Extraction complete for PI: %s", profile.pi_name)
    return profile
