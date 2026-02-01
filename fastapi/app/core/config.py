import secrets
from pathlib import Path
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    # App settings
    PROJECT_NAME: str = "Desktop App"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["local", "development", "production"] = "local"

    # Auth settings (opt-in, disabled by default for desktop)
    AUTH_REQUIRED: bool = False
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database settings (SQLite)
    # DATA_DIR is passed from Tauri (app_data_dir) or defaults to current directory
    DATA_DIR: Path = Path(".")
    DATABASE_NAME: str = "app.db"

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        db_path = self.DATA_DIR / self.DATABASE_NAME
        return f"sqlite:///{db_path}"

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 1430

    # Default user settings (used when AUTH_REQUIRED=False)
    DEFAULT_USER_EMAIL: str = "local@desktop.app"
    DEFAULT_USER_NAME: str = "Local User"


settings = Settings()
