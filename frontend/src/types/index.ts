export type Perfil = 'vendedor' | 'proprietaria';

export type LoginResponse = {
  token: string;
  perfil: Perfil;
};

export type ConfiancaGps = 'alta' | 'media' | 'baixa';
export type GpsSource = 'live' | 'warm';

export type Cliente = {
  id: string;
  nome: string;
  latitude: number;
  longitude: number;
  ativo: boolean;
  criado_em: string;
  distancia_metros?: number | null;
};

export type ClienteSugestao = {
  cliente: Cliente;
  confianca: ConfiancaGps;
};

/** Body for `POST /clientes` with GPS capture metadata from the vendedor cadastro flow. */
export type ClienteCadastroPayload = {
  nome: string;
  latitude: number;
  longitude: number;
  gps_accuracy_media: number;
  gps_accuracy_min: number;
  gps_amostras: number;
};

export type ClienteMaisProximoResponse = {
  tem_clientes: boolean;
  raio_busca_metros: number;
  distancia_metros?: number | null;
  cliente?: Cliente | null;
};

/** Campos extras aceitos por `POST /registros` (auditoria / aprendizado). */
export type RegistroCreateMetadata = {
  data_entrega?: string | null;
  gps_accuracy_registro?: number | null;
  gps_source?: GpsSource | null;
  cliente_sugerido_id?: string | null;
  candidatos_ids?: string[] | null;
  aprendizado_permitido?: boolean | null;
};

export type Registro = {
  id: string;
  cliente_id: string;
  cliente_nome: string;
  deixou: number;
  tinha: number;
  trocas: number;
  vendido: number;
  data: string;
  hora: string;
  latitude_registro: number;
  longitude_registro: number;
  registrado_por: string;
};

export type DashboardResumo = {
  total_deixou_hoje: number;
  total_vendido_hoje: number;
  total_trocas_hoje: number;
  clientes_visitados_hoje: number;
  total_clientes_ativos: number;
};

export type SemaphoreLevel = {
  nivel: 'verde' | 'amarelo' | 'vermelho';
  sobra_pct: number | null;
};

export type DashboardClienteCard = {
  cliente_id: string;
  nome: string;
  ultima_visita: string | null;
  media_deixou_4sem: number | null;
  media_vendido_4sem: number | null;
  media_trocas_4sem: number | null;
  sobra_media_pct: number | null;
  semaforo: SemaphoreLevel;
};

export type DashboardResponse = {
  resumo: DashboardResumo;
  clientes: DashboardClienteCard[];
};

export type ResumoSemanalLinha = {
  cliente_id: string;
  cliente_nome: string;
  total_deixou: number;
  total_vendido: number;
  total_trocas: number;
  aproveitamento_pct: number | null;
  sugestao: '+5' | 'manter' | '-5' | '-10';
};

export type ResumoSemanalResponse = {
  ano: number;
  semana: number;
  inicio: string;
  fim: string;
  linhas: ResumoSemanalLinha[];
};
