from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # n8n
    N8N_BASE_URL: str = "https://kj-autonomous.up.railway.app"
    N8N_EMAIL: str = ""
    N8N_PASSWORD: str = ""
    N8N_API_KEY: str = ""

    # Asterisk / AVA
    ASTERISK_VPS_IP: str = "192.161.173.97"
    ASTERISK_ARI_USER: str = "asterisk"
    ASTERISK_ARI_PASS: str = "asterisk"

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = "+18666217044"

    # Resend
    RESEND_API_KEY: str = ""

    # Lob
    LOB_API_KEY: str = ""

    # OpenAI
    OPENAI_API_KEY: str = ""

    # KJLE
    KJLE_API_URL: str = "https://kjle-api.onrender.com"
    KJLE_API_KEY: str = ""

    # Google Business Profile
    GOOGLE_BUSINESS_API_KEY: str = ""

    # VoiceDrop
    VOICEDROP_API_KEY: str = ""

    # R2
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_ACCOUNT_ID: str = ""
    R2_BUCKET: str = "agentenginez-reports"
    R2_PUBLIC_BASE: str = ""

    # App
    APP_BASE_URL: str = "http://localhost:8000"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
