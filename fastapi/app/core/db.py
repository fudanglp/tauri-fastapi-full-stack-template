import time
from collections.abc import Generator

from loguru import logger
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings

# Create engine with SQLite-specific settings
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False},  # Required for SQLite with FastAPI
)


# SQL query logging via SQLAlchemy events (only in local dev)
if settings.ENVIRONMENT == "local":

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = (time.time() - conn.info["query_start_time"].pop(-1)) * 1000
        # Log SQL on single line with parameters
        sql = " ".join(statement.split())  # Collapse whitespace/newlines
        if parameters:
            sql = f"{sql} {parameters}"
        logger.info(f"SQL ({total:.2f}ms): {sql}")


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
    """Configure SQLite for better performance and data integrity."""
    cursor = dbapi_connection.cursor()
    # WAL mode for better concurrency (allows reads while writing)
    cursor.execute("PRAGMA journal_mode=WAL")
    # Enable foreign key enforcement (off by default in SQLite)
    cursor.execute("PRAGMA foreign_keys=ON")
    # Wait up to 5 seconds if database is locked
    cursor.execute("PRAGMA busy_timeout=5000")
    # Synchronous mode: NORMAL is a good balance of safety and speed
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_session() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    with Session(engine) as session:
        yield session


def init_db(session: Session) -> None:
    """
    Initialize database with default data.
    Called after migrations have been applied.
    """
    from app import crud
    from app.models import User

    # Create default local user if AUTH_REQUIRED is False
    if not settings.AUTH_REQUIRED:
        user = session.exec(
            select(User).where(User.email == settings.DEFAULT_USER_EMAIL)
        ).first()
        if not user:
            user = crud.get_or_create_default_user(
                session=session,
                email=settings.DEFAULT_USER_EMAIL,
                full_name=settings.DEFAULT_USER_NAME,
            )
