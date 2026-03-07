from typing import Annotated
from pydantic import BaseModel, HttpUrl, field_validator, Field


class LabProfile(BaseModel):
    pi_name: str = Field(..., description="Full name of the Principal Investigator")
    institution: str = Field(..., description="University or research institution name")
    faculty: str = Field(..., description="Department or faculty the lab belongs to")
    research_summary: Annotated[
        list[str],
        Field(..., description="Exactly 3 bullet points summarising the lab's research"),
    ]
    keywords: Annotated[
        list[str],
        Field(..., description="Exactly 5 technical keyword tags for the lab"),
    ]
    technologies: Annotated[
        list[str],
        Field(
            ...,
            description=(
                "Research domains, buzz words, and topics users might search for. "
                "Include methodologies, techniques, and broad themes (e.g. Large Language Models, "
                "fMRI, Reinforcement Learning, Semantic Parsing, psychedelics, CRISPR). "
                "Do NOT include specific software, languages, or packages (e.g. Python, PyTorch)."
            ),
        ),
    ]
    hiring_status: str | bool = Field(
        ...,
        description=(
            "Whether the lab is actively looking for students. "
            "Use True/False if unambiguous, or a short descriptive string."
        ),
    )
    lab_url: HttpUrl = Field(..., description="Canonical URL of the lab page")
    representative_papers: list[str] = Field(
        default_factory=list,
        description=(
            "Representative paper titles for author disambiguation. "
            "Extract when listed on the lab page (e.g. Publications, Selected Works). "
            "Used to match the correct author in Semantic Scholar when affiliations are missing."
        ),
    )

    @field_validator("research_summary")
    @classmethod
    def validate_research_summary_length(cls, v: list[str]) -> list[str]:
        if not (2 <= len(v) <= 5):
            raise ValueError(
                f"research_summary must have 2–5 items, got {len(v)}"
            )
        return v

    @field_validator("keywords")
    @classmethod
    def validate_keywords_length(cls, v: list[str]) -> list[str]:
        if not (3 <= len(v) <= 8):
            raise ValueError(
                f"keywords must have 3–8 tags, got {len(v)}"
            )
        return v

    @field_validator("technologies")
    @classmethod
    def validate_technologies_length(cls, v: list[str]) -> list[str]:
        if not (0 <= len(v) <= 15):
            raise ValueError(
                f"technologies must have 0–15 items, got {len(v)}"
            )
        return v


class ExtractRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL of the faculty/lab page to scrape")


class ExtractResponse(BaseModel):
    success: bool
    data: LabProfile | None = None
    error: str | None = None
