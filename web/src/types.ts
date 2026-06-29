export type ResumoAno = {
  ano: number;
  registros: number;
  municipios: number;
  periodo: [string, string];
};

export type MunicipioCount = {
  codarea: string;
  municipio: string;
  notificacoes: number;
  cluster?: number;
  casosSemana?: number;
  uf?: string;
};

export type SemanalData = {
  weekly: { semana: number; casos: number }[];
  assignments: Record<string, Record<string, number>>;
  weeklyCounts?: Record<string, Record<string, number>>;
};

export const CLUSTER_COLORS = ["#1b7837", "#2166ac", "#762a83", "#b2182b"] as const;
export const CLUSTER_NOMES = ["Baixo", "Médio-", "Médio+", "Alto"] as const;
