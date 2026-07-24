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
    heygen_api_key: str | None = None
    runway_api_key: str | None = None
    ai_lab_base_url: str | None = None  # AI LAB Service (Sprint 26), e.g. http://localhost:8000
    ai_lab_api_key: str | None = None
    # Biblioteca Inteligente de Marketing (FASE 2.3) — storage S3-compatible generico
    # (Cloudflare R2, AWS S3, Backblaze B2, Supabase Storage, etc). Sin estos valores
    # configurados, src/library_storage.py lanza LibraryStorageNotConfiguredError.
    library_s3_endpoint_url: str | None = None
    library_s3_bucket: str | None = None
    library_s3_access_key_id: str | None = None
    library_s3_secret_access_key: str | None = None
    library_s3_region: str = "auto"
    library_s3_public_base_url: str | None = None  # si no esta seteado, se usan presigned URLs
    # Webhook de comentarios de Instagram (respuesta publica + DM privado por
    # palabra clave) — ver POST/GET /webhooks/instagram en src/main.py.
    instagram_webhook_verify_token: str | None = None
    meta_app_secret: str | None = None
    instagram_dm_trigger_keyword: str = "QUERO"
    instagram_dm_reply_text: str | None = None
    instagram_comment_reply_text: str = "Te mandei por mensagem privada! 📩 Confere sua caixa de entrada."


settings = Settings()
