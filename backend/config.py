import base64
import json
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from exceptions import ServiceAccountConfigError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    google_sheets_id: str
    google_service_account_json: str

    # Alias JWT_SFCRFT: typo comum ao copiar variáveis no Railway
    jwt_secret: str = Field(
        default="dev-secret-change-me",
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SFCRFT"),
    )
    jwt_expiration_hours: int = 24

    cors_origins: str = "http://localhost:5173"
    # Opcional: regex para previews Vercel (ex.: https://.*\.vercel\.app)
    cors_origin_regex: str = ""

    vendedor_email: str
    vendedor_password_hash: str = ""
    # Alias PROPRIETARIA_EMATL: typo comum
    proprietaria_email: str = Field(validation_alias=AliasChoices("PROPRIETARIA_EMAIL", "PROPRIETARIA_EMATL"))
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
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                raise ServiceAccountConfigError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON: JSON direto inválido ou truncado. "
                    "Prefira colar o arquivo inteiro em base64 (uma linha), gerado com: base64 -w0 chave.json. "
                    f"Erro: {e}"
                ) from e

        # Remove espaços/quebras — o painel do Railway costuma quebrar linhas no meio do base64
        b64 = "".join(raw.split())
        try:
            decoded = base64.b64decode(b64, validate=False).decode("utf-8")
        except Exception as e:
            raise ServiceAccountConfigError(
                "GOOGLE_SERVICE_ACCOUNT_JSON: não é base64 válido. "
                "No terminal: base64 -w0 service-account.json e cole o resultado inteiro em UMA variável, sem aspas. "
                f"Erro: {e}"
            ) from e

        try:
            return json.loads(decoded)
        except json.JSONDecodeError as e:
            raise ServiceAccountConfigError(
                "GOOGLE_SERVICE_ACCOUNT_JSON: o base64 decodificou, mas o JSON da service account está quebrado "
                "(valor cortado, aspas erradas ou quebra de linha dentro da private_key). "
                "Baixe de novo o JSON no Google Cloud e regenere: base64 -w0 arquivo.json — uma linha só no Railway. "
                f"Erro: {e}"
            ) from e


@lru_cache
def get_settings() -> Settings:
    return Settings()
