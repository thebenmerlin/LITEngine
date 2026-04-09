import sys
from loguru import logger


def setup_logger(log_level: str = "INFO") -> None:
    """Configure loguru with a clean, production-ready format."""
    # Remove default handler
    logger.remove()

    # Console handler with colored output
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File handler with rotation (logs/lit-backend.log)
    logger.add(
        "logs/lit_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        level="DEBUG",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} - "
            "{message}"
        ),
    )


def get_logger(name: str = __name__):
    """Return a logger bound to a specific context."""
    return logger.bind(name=name)


# Initialize logger on import with default level
setup_logger()
