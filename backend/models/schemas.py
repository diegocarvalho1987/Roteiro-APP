from typing import Literal

from pydantic import BaseModel, Field, field_validator


Perfil = Literal["vendedor", "proprietaria"]
ConfiancaGps = Literal["alta", "media", "baixa"]
GpsSource = Literal["live", "warm"]


class LoginRequest(BaseModel):
    email: str
    senha: str


class LoginResponse(BaseModel):
    token: str
    perfil: Perfil


class ClienteCreate(BaseModel):
    nome: str = Field(min_length=1)
    latitude: float
    longitude: float
    # Metadados opcionais da captura GPS no app (média / mínimo em metros, contagem de amostras).
    gps_accuracy_media: float | None = Field(default=None, ge=0)
    gps_accuracy_min: float | None = Field(default=None, ge=0)
    gps_amostras: int | None = Field(default=None, ge=1)

    def has_gps_metadata(self) -> bool:
        return any(
            value is not None
            for value in (self.gps_accuracy_media, self.gps_accuracy_min, self.gps_amostras)
        )


class ClienteUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    ativo: bool | None = None


class ClienteResponse(BaseModel):
    id: str
    nome: str
    latitude: float
    longitude: float
    ativo: bool
    criado_em: str
    distancia_metros: float | None = None


class ClienteMaisProximoResponse(BaseModel):
    """Cliente ativo mais próximo do ponto (para explicar fallback manual)."""

    tem_clientes: bool
    raio_busca_metros: float
    distancia_metros: float | None = None
    cliente: ClienteResponse | None = None


class ClienteSugestao(BaseModel):
    """Sugestão de cliente com nível de confiança derivado da qualidade do GPS."""

    cliente: ClienteResponse
    confianca: ConfiancaGps


class RegistroCreate(BaseModel):
    cliente_id: str
    deixou: int = Field(ge=0)
    tinha: int = Field(ge=0)
    trocas: int = Field(ge=0)
    latitude_registro: float
    longitude_registro: float
    # Metadados opcionais para auditoria / aprendizado de posição.
    gps_accuracy_registro: float | None = Field(default=None, ge=0)
    gps_source: GpsSource | None = None
    cliente_sugerido_id: str | None = None
    candidatos_ids: list[str] | None = None
    aprendizado_permitido: bool | None = None

    @field_validator("cliente_id", "cliente_sugerido_id", "gps_source")
    @classmethod
    def _strip_non_empty_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("ID não pode ser vazio")
        return stripped

    @field_validator("candidatos_ids")
    @classmethod
    def _validate_candidatos_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            stripped = item.strip()
            if not stripped:
                raise ValueError("candidatos_ids não pode conter itens vazios")
            if stripped in seen:
                raise ValueError("candidatos_ids não pode conter IDs duplicados")
            seen.add(stripped)
            cleaned.append(stripped)
        return cleaned

    def has_audit_metadata(self) -> bool:
        return any(
            value is not None
            for value in (
                self.gps_accuracy_registro,
                self.gps_source,
                self.cliente_sugerido_id,
                self.candidatos_ids,
                self.aprendizado_permitido,
            )
        )


class RegistroResponse(BaseModel):
    id: str
    cliente_id: str
    cliente_nome: str
    deixou: int
    tinha: int
    trocas: int
    vendido: int
    data: str
    hora: str
    latitude_registro: float
    longitude_registro: float
    registrado_por: str


class DashboardResumo(BaseModel):
    total_deixou_hoje: int
    total_vendido_hoje: int
    total_trocas_hoje: int
    clientes_visitados_hoje: int
    total_clientes_ativos: int


class SemaphoreLevel(BaseModel):
    nivel: Literal["verde", "amarelo", "vermelho"]
    sobra_pct: float | None


class DashboardClienteCard(BaseModel):
    cliente_id: str
    nome: str
    ultima_visita: str | None
    media_deixou_4sem: float | None
    media_vendido_4sem: float | None
    media_trocas_4sem: float | None
    sobra_media_pct: float | None
    semaforo: SemaphoreLevel


class DashboardResponse(BaseModel):
    resumo: DashboardResumo
    clientes: list[DashboardClienteCard]


class ResumoSemanalLinha(BaseModel):
    cliente_id: str
    cliente_nome: str
    total_deixou: int
    total_vendido: int
    total_trocas: int
    aproveitamento_pct: float | None
    sugestao: Literal["+5", "manter", "-5", "-10"]


class ResumoSemanalResponse(BaseModel):
    ano: int
    semana: int
    inicio: str
    fim: str
    linhas: list[ResumoSemanalLinha]
