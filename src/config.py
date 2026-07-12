from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/iea_agentiq"
    redis_url: str = "redis://localhost:6379/0"
    admin_user: str = "admin"
    admin_password: str = "change-me"
    anthropic_api_key: str | None = None
    secret_key: str = "dev-secret-change-me"
    composio_api_key: str | None = None
    serper_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None  # Used for Lisa Mawu by default
    ai_lab_base_url: str | None = None  # AI LAB Service (Sprint 26), e.g. http://localhost:8000
    ai_lab_api_key: str | None = None


settings = Settings()
