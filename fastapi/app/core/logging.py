import logging
import sys

from loguru import logger


def log_format(record: dict) -> str:
    """Custom format that handles both loguru and intercepted logs."""
    # Check if this is an intercepted log (has 'name' in extra)
    if "name" in record["extra"]:
        name = record["extra"]["name"]
        return (
            "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
            f"<cyan>{name}</cyan> - <level>{{message}}</level>\n"
        )
    else:
        return (
            "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"
        )


class InterceptHandler(logging.Handler):
    """
    Intercept standard logging and redirect to loguru.
    This ensures uvicorn, alembic, and other libraries use loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Log with the original logger name from the record
        logger.bind(name=record.name).opt(exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(level: str = "INFO") -> None:
    """
    Configure loguru as the main logger and intercept standard logging.

    Args:
        level: Minimum log level to display
    """
    # Remove default loguru handler
    logger.remove()

    # Add custom handler with dynamic formatting
    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=True,
    )

    # Intercept standard logging (for uvicorn, alembic, etc.)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Silence SQLAlchemy's default logger (we use events for SQL logging)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
