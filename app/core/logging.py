import sys
from loguru import logger
from app.core.config import settings


def setup_logging() -> None:
    logger.remove()  # Remove default handler

    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # Persistent file log in production
    if settings.is_production:
        logger.add(
            "logs/brd_agent_{time:YYYY-MM-DD}.log",
            level="INFO",
            rotation="00:00",       # New file each day
            retention="30 days",
            compression="zip",
            format="{time} | {level} | {name}:{line} | {message}",
        )
