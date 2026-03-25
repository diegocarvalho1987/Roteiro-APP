import type { ClienteSugestao, ConfiancaGps } from '../types';

/** Ordem para comparar confiança (menor = melhor). */
const CONFIANCA_RANK: Record<ConfiancaGps, number> = {
  alta: 0,
  media: 1,
  baixa: 2,
};

export function compareConfianca(a: ConfiancaGps, b: ConfiancaGps): number {
  return CONFIANCA_RANK[a] - CONFIANCA_RANK[b];
}

/** Rótulo curto para exibição na UI. */
export function labelConfianca(confianca: ConfiancaGps): string {
  switch (confianca) {
    case 'alta':
      return 'Alta';
    case 'media':
      return 'Média';
    case 'baixa':
      return 'Baixa';
  }
}

export function formatarDistancia(metros: number): string {
  if (metros >= 1000) return `${(metros / 1000).toFixed(1)} km`;
  return `${Math.round(metros)} m`;
}

/**
 * O backend ordena por distância crescente; o candidato mais provável é sempre o primeiro.
 * Retorna -1 se não houver sugestões.
 */
export function indexMaisProvavel(sugestoes: ClienteSugestao[]): number {
  if (sugestoes.length === 0) return -1;
  return 0;
}
