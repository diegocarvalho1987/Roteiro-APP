import base64
import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    google_sheets_id: str
    google_service_account_json: str

    jwt_secret: str = "dev-secret-change-me"
    jwt_expiration_hours: int = 24

    cors_origins: str = "http://localhost:5173"

    vendedor_email: str
    vendedor_password_hash: str = ""
    proprietaria_email: str
    proprietaria_password_hash: str = ""

    allow_plain_passwords: bool = False
    vendedor_password: str = ""
    proprietaria_password: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def service_account_info(self) -> dict:
        raw = self.google_service_account_json.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        decoded = base64.b64decode(raw).decode("utf-8")
        return json.loads(decoded)


@lru_cache
def get_settings() -> Settings:
    return Settings()
