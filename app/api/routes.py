"""
POST /api/v1/generate-brd

Orchestrates the full pipeline:
  validate → extract → ai_process → build → base64 encode → respond

Error mapping:
  ExtractionError   → 400
  AIProcessorError  → 422
  AzureFoundryError → 502  (upstream Azure failure — retries exhausted)
  BRDBuilderError   → 500
  Unhandled         → 500
"""
import base64
import os
import uuid
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from loguru import logger

from app.api.dependencies import validate_upload_file, verify_api_key
from app.core.models import BRDResponse, ErrorResponse
from app.services.ai_processor import AIProcessorError, process_transcript
from app.services.brd_builder import BRDBuilderError, build_brd
from app.services.extractor import ExtractionError, extract_transcript
from app.services.foundry_client import AzureFoundryError

router = APIRouter()


@router.post(
    "/generate-brd",
    response_model=BRDResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad file or extraction failure"},
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "AI returned unprocessable output"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        502: {"model": ErrorResponse, "description": "Azure AI Foundry upstream error"},
    },
    summary="Generate BRD from transcript",
)
async def generate_brd(
    file: UploadFile,
    raw_bytes: bytes = Depends(validate_upload_file),
    _: str = Depends(verify_api_key),
) -> BRDResponse:
    job_id = str(uuid.uuid4())
    filename = file.filename or "transcript.vtt"
    _, ext = os.path.splitext(filename)
    start = datetime.now(timezone.utc)

    logger.info("BRD job started", job_id=job_id, filename=filename, size=len(raw_bytes))

    # ------------------------------------------------------------------
    # Layer 1 — Transcript extraction
    # ------------------------------------------------------------------
    try:
        transcript_text = extract_transcript(raw_bytes, filename)
    except ExtractionError as exc:
        logger.warning("Extraction failed", job_id=job_id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # ------------------------------------------------------------------
    # Layer 2 — AI processing
    # ------------------------------------------------------------------
    try:
        brd_content = await asyncio.to_thread(process_transcript, transcript_text)
    except AzureFoundryError as exc:
        logger.error("Azure Foundry error", job_id=job_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure AI Foundry error: {exc}",
        )
    except AIProcessorError as exc:
        logger.error("AI processor error", job_id=job_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # ------------------------------------------------------------------
    # Layer 3 — BRD document build
    # ------------------------------------------------------------------
    try:
        docx_bytes = build_brd(brd_content)
    except BRDBuilderError as exc:
        logger.error("BRD builder error", job_id=job_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    # ------------------------------------------------------------------
    # Response
    # ------------------------------------------------------------------
    docx_b64 = base64.b64encode(docx_bytes).decode("utf-8")
    elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    project_slug = (
        brd_content.project_name.replace(" ", "_").lower()
        if brd_content.project_name
        else "brd"
    )
    output_filename = f"{project_slug}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.docx"

    sections_extracted = {
        "business_objectives": len(brd_content.business_objectives),
        "in_scope": len(brd_content.in_scope),
        "out_of_scope": len(brd_content.out_of_scope),
        "functional_requirements": len(brd_content.functional_requirements),
        "non_functional_requirements": len(brd_content.non_functional_requirements),
        "assumptions": len(brd_content.assumptions),
        "constraints": len(brd_content.constraints),
        "risks": len(brd_content.risks),
    }

    logger.info(
        "BRD job complete",
        job_id=job_id,
        elapsed_ms=elapsed_ms,
        docx_bytes=len(docx_bytes),
        sections=sections_extracted,
    )

    return BRDResponse(
        success=True,
        job_id=job_id,
        project_name=brd_content.project_name or "Unknown Project",
        filename=output_filename,
        docx_base64=docx_b64,
        sections_extracted=sections_extracted,
    )
