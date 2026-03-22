from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.models.lab import ExtractRequest, ExtractResponse
from app.services.extractor import extract_lab_data
from app.services.lab_crawler import crawl_lab_with_nested

router = APIRouter(prefix="", tags=["extraction"])


@router.post(
    "/extract",
    response_model=ExtractResponse,
    summary="Extract structured lab data from a URL",
    description=(
        "Crawl the given URL, convert HTML to Markdown, then use an LLM agent "
        "to extract a structured LabProfile JSON."
    ),
)
async def extract(body: ExtractRequest) -> ExtractResponse:
    url = str(body.url)

    try:
        markdown = await crawl_lab_with_nested(url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        profile = await extract_lab_data(markdown, url)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"LLM returned data that failed schema validation: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM extraction failed: {exc}",
        ) from exc

    return ExtractResponse(success=True, data=profile)
