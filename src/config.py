from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/iea_agentiq"
    redis_url: str = "redis://localhost:6379/0"
    admin_user: str = "admin"
    admin_password: str = "change-me"

    supabase_url: str = "https://djyuotgzcwhqvoowvixv.supabase.co"
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    secret_key: str = "dev_secret_key_change_in_production"
    environment: str = "development"
    debug: bool = True
    api_title: str = "AGENTIQ Agents Platform"
    api_version: str = "1.0.0"
    allowed_origins: str = "http://localhost:3000,http://localhost:8000,http://localhost:5173"


settings = Settings()
