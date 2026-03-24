from typing import Literal

from pydantic import BaseModel, Field


Perfil = Literal["vendedor", "proprietaria"]


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


class RegistroCreate(BaseModel):
    cliente_id: str
    deixou: int = Field(ge=0)
    tinha: int = Field(ge=0)
    trocas: int = Field(ge=0)
    latitude_registro: float
    longitude_registro: float


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
