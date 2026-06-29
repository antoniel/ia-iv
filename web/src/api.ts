import type { ResumoAno, SemanalData, MunicipioCount } from "./types";
import type { FeatureCollection } from "geojson";

export const NORDESTE_UFS = [
  "MA",
  "PI",
  "CE",
  "RN",
  "PB",
  "PE",
  "AL",
  "SE",
  "BA",
] as const;

/** Valor do select quando o mapa mostra todos os estados vigentes. */
export const UF_TODOS = "TODOS";

export type StateMeta = {
  uf: string;
  nome: string;
  ibge: number;
  geo_ready: boolean;
  resumo_ready: boolean;
  municipios_ready: boolean;
  ready: boolean;
};

export type ClusterParams = {
  k: number;
  min_casos: number;
};

export type SemanalResponse = SemanalData & {
  cached: boolean;
  params?: ClusterParams & { uf: string; ano: number };
};

export type RegionResumoRow = {
  uf: string;
  nome: string;
  ano: number;
  registros: number;
  municipios: number;
  periodo: [string, string];
};

export type RegionClusterResult = {
  weekly: { semana: number; casos: number }[];
  clusterByUf: Record<string, Record<string, Record<string, number>>>;
  weeklyCountsByUf: Record<string, Record<string, Record<string, number>>>;
  ufs: string[];
  cached: boolean;
};

const BASE = "/api";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json();
}

export function fetchAnos() {
  return getJson<{ anos: number[] }>(`${BASE}/meta/anos`);
}

export function fetchStates(ano: number) {
  return getJson<{ region: string; states: StateMeta[]; ready: string[]; ano: number }>(
    `${BASE}/meta/states?ano=${ano}`,
  );
}

export function fetchRegionGeo(ano: number) {
  return getJson<{ ufs: string[]; geo: FeatureCollection }>(
    `${BASE}/region/geo?ano=${ano}`,
  );
}

export function fetchRegionMunicipios(ano: number) {
  return getJson<{ ufs: string[]; municipios: MunicipioCount[] }>(
    `${BASE}/region/municipios?ano=${ano}`,
  );
}

export function fetchRegionResumoAno(ano: number) {
  return getJson<{ ano: number; states: RegionResumoRow[] }>(
    `${BASE}/region/resumo-ano?ano=${ano}`,
  );
}

export function fetchResumo(uf: string, ano: number) {
  return getJson<ResumoAno[]>(`${BASE}/${uf}/resumo?ano=${ano}`);
}

export function fetchClusterWeekly(
  uf: string,
  ano: number,
  params: ClusterParams,
): Promise<SemanalResponse> {
  const q = new URLSearchParams({
    ano: String(ano),
    k: String(params.k),
    min_casos: String(params.min_casos),
  });
  return getJson(`${BASE}/${uf}/cluster/weekly?${q}`);
}

export async function fetchClusterRegion(
  ufs: string[],
  ano: number,
  params: ClusterParams,
): Promise<RegionClusterResult> {
  const results = await Promise.allSettled(
    ufs.map((uf, i) => {
      console.info(`[cluster] ${i + 1}/${ufs.length} ${uf}`);
      return fetchClusterWeekly(uf, ano, params);
    }),
  );

  const okUfs: string[] = [];
  const clusterByUf: RegionClusterResult["clusterByUf"] = {};
  const weeklyCountsByUf: RegionClusterResult["weeklyCountsByUf"] = {};
  const weekTotals = new Map<number, number>();
  let allCached = true;

  results.forEach((result, i) => {
    const uf = ufs[i];
    if (result.status !== "fulfilled") return;
    okUfs.push(uf);
    clusterByUf[uf] = result.value.assignments;
    weeklyCountsByUf[uf] = result.value.weeklyCounts ?? {};
    if (!result.value.cached) allCached = false;
    for (const w of result.value.weekly) {
      weekTotals.set(w.semana, (weekTotals.get(w.semana) ?? 0) + w.casos);
    }
  });

  const weekly = [...weekTotals.entries()]
    .sort(([a], [b]) => a - b)
    .map(([semana, casos]) => ({ semana, casos }));

  return { weekly, clusterByUf, weeklyCountsByUf, ufs: okUfs, cached: allCached };
}
