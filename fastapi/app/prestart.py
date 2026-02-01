"""
Prestart script: run migrations and initialize data.
Called on application startup before serving requests.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Run alembic migrations to head."""
    logger.info("Running database migrations...")

    # Ensure data directory exists
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Find alembic.ini relative to this file
    # app/prestart.py -> app/ -> fastapi/ -> alembic.ini
    app_dir = Path(__file__).parent
    fastapi_dir = app_dir.parent
    alembic_ini = fastapi_dir / "alembic.ini"

    if not alembic_ini.exists():
        logger.warning(f"alembic.ini not found at {alembic_ini}, skipping migrations")
        return

    alembic_cfg = Config(str(alembic_ini))
    # Override script_location to be absolute path
    alembic_cfg.set_main_option("script_location", str(app_dir / "alembic"))

    command.upgrade(alembic_cfg, "head")
    logger.info("Migrations complete")


def run_initial_data() -> None:
    """Initialize database with default data."""
    logger.info("Initializing data...")
    from app.initial_data import init

    init()
    logger.info("Data initialization complete")


def main() -> None:
    """Run all prestart tasks."""
    run_migrations()
    run_initial_data()


if __name__ == "__main__":
    main()
