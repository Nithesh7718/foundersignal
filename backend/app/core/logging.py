import logging
import sys

from app.core.config import settings


def setup_logging() -> logging.Logger:
    level = logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger("foundersignal")
    logger.setLevel(level)

    # Avoid duplicate handlers if reloaded
    if not logger.handlers:
        logger.addHandler(handler)

    return logger


logger = setup_logging()
