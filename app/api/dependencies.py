from fastapi import Header, HTTPException, UploadFile, status
from loguru import logger
from app.core.config import settings


async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return x_api_key


async def validate_upload_file(file: UploadFile) -> bytes:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    allowed = (
        settings.allowed_extensions
        if isinstance(settings.allowed_extensions, list)
        else [e.strip() for e in settings.allowed_extensions.split(",")]
    )

    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {settings.allowed_extensions}",
        )

    raw = await file.read()

    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds {settings.max_file_size_mb}MB limit.",
        )

    logger.debug(f"File validated: {file.filename} ({len(raw)} bytes)")
    return raw
