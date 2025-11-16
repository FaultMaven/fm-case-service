"""Service configuration settings."""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service configuration
    service_name: str = "fm-case-service"
    environment: str = "development"
    port: int = 8003

    # Database configuration
    database_url: str = "sqlite+aiosqlite:///./fm_cases.db"

    # Pagination defaults
    default_page_size: int = 50
    max_page_size: int = 100

    # CORS configuration
    cors_origins: str = "*"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
