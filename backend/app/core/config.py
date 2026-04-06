from pathlib import Path
import os
from urllib.parse import urlparse, urlunparse

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Appointment MCP Tracker"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, validation_alias="PORT")
    frontend_origin: str = "http://localhost:5173"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/appointment_mcp"

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_max_tokens: int = 1200

    mcp_server_url: str = ""

    google_calendar_id: str = "primary"
    google_access_token: str = ""
    google_refresh_token: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_token_url: str = "https://oauth2.googleapis.com/token"
    google_timezone: str = "Asia/Kolkata"

    email_provider: str = "sendgrid"
    email_from: str = "no-reply@clinic.local"
    email_api_key: str = ""

    whatsapp_provider: str = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    doctor_whatsapp_to: str = ""

    default_doctor_login_email: str = "doctor@clinic.local"
    default_doctor_login_password: str = "doctor123"

    @model_validator(mode="after")
    def _normalize_and_validate_database_url(self):
        url = (self.database_url or "").strip()
        if url.startswith("postgres://"):
            # Render/Heroku-style URL; SQLAlchemy + psycopg expects postgresql+psycopg.
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            # Some providers expose postgresql:// URL without an explicit DBAPI driver.
            url = "postgresql+psycopg://" + url[len("postgresql://") :]

        is_render = (os.getenv("RENDER") or "").lower() in {"true", "1", "yes"}
        if is_render and (not url or "localhost" in url or "127.0.0.1" in url):
            raise ValueError(
                "DATABASE_URL is not configured for Render. Set it to your Render PostgreSQL internal URL "
                "(postgresql+psycopg://...@...:5432/...)."
            )

        self.database_url = url

        # Normalize MCP endpoint so internal calls work in local and cloud runtimes.
        mcp_url = (self.mcp_server_url or "").strip().rstrip("/")
        if not mcp_url:
            runtime_port = os.getenv("PORT") or str(self.app_port)
            mcp_url = f"http://127.0.0.1:{runtime_port}/mcp"

        if not mcp_url.endswith("/mcp"):
            mcp_url = f"{mcp_url}/mcp"

        parsed = urlparse(mcp_url)
        if parsed.hostname in {"127.0.0.1", "localhost"}:
            runtime_port = os.getenv("PORT")
            if runtime_port:
                host = parsed.hostname or "127.0.0.1"
                parsed = parsed._replace(netloc=f"{host}:{runtime_port}")
                mcp_url = urlunparse(parsed)

        self.mcp_server_url = mcp_url
        return self


settings = Settings()
