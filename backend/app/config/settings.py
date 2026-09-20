"""Configuration loaded from the environment and an optional local .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Provider credentials remain optional until their phases ship."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./smart_messages.db", validation_alias="DATABASE_URL"
    )
    app_session_secret: str = Field(
        default="local-development-only-change-before-oauth",
        validation_alias="APP_SESSION_SECRET",
    )
    frontend_origin: str = Field(
        default="http://localhost:5173", validation_alias="FRONTEND_ORIGIN"
    )

    @property
    def frontend_origins(self) -> list[str]:
        """Comma-separated FRONTEND_ORIGIN values (e.g. localhost plus a LAN IP for mobile access)."""
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    azure_openai_endpoint: str | None = Field(default=None, validation_alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str | None = Field(default=None, validation_alias="AZURE_OPENAI_API_KEY")
    azure_openai_chat_deployment: str | None = Field(
        default=None, validation_alias="AZURE_OPENAI_CHAT_DEPLOYMENT"
    )
    azure_openai_embedding_deployment: str | None = Field(
        default=None, validation_alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )
    azure_search_endpoint: str | None = Field(default=None, validation_alias="AZURE_SEARCH_ENDPOINT")
    azure_search_api_key: str | None = Field(default=None, validation_alias="AZURE_SEARCH_API_KEY")
    azure_search_index: str | None = Field(default=None, validation_alias="AZURE_SEARCH_INDEX")

    google_client_id: str | None = Field(default=None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str | None = Field(default=None, validation_alias="GOOGLE_REDIRECT_URI")

    @property
    def oauth_session_is_safe(self) -> bool:
        return (
            self.app_session_secret != "local-development-only-change-before-oauth"
            and len(self.app_session_secret) >= 32
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
