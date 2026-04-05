from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Appointment MCP Tracker"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/appointment_mcp"

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_max_tokens: int = 1200

    mcp_server_url: str = "http://127.0.0.1:8000/mcp"

    google_calendar_id: str = "primary"
    google_access_token: str = ""
    google_timezone: str = "Asia/Kolkata"

    email_provider: str = "sendgrid"
    email_from: str = "no-reply@clinic.local"
    email_api_key: str = ""

    whatsapp_provider: str = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    doctor_whatsapp_to: str = ""


settings = Settings()
