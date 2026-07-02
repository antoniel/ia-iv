import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  fetchAnos,
  fetchClusterRegion,
  fetchResumo,
  fetchStates,
  NORDESTE_UFS,
  UF_TODOS,
  type StateMeta,
} from "./api";
import ChoroplethMap from "./components/ChoroplethMap";
import { ChartAnos, ChartClusterCounts, ChartSemanas } from "./components/Charts";
import SectionLoader from "./components/SectionLoader";
import { useRegionData } from "./hooks/useData";
import { CLUSTER_COLORS, CLUSTER_NOMES, type ResumoAno } from "./types";
import type { FeatureCollection } from "geojson";

const UF_NOMES: Record<string, string> = {
  MA: "Maranhão",
  PI: "Piauí",
  CE: "Ceará",
  RN: "Rio Grande do Norte",
  PB: "Paraíba",
  PE: "Pernambuco",
  AL: "Alagoas",
  SE: "Sergipe",
  BA: "Bahia",
};

const MIN_CASOS = 30;

function fmt(n: number) {
  return n.toLocaleString("pt-BR");
}

function Chapter({
  title,
  loading,
  loadingLabel,
  children,
}: {
  title: string;
  loading?: boolean;
  loadingLabel?: string;
  children: ReactNode;
}) {
  return (
    <section className="chapter">
      <h2>{title}</h2>
      {loading ? (
        <SectionLoader label={loadingLabel ?? "Carregando…"} />
      ) : (
        children
      )}
    </section>
  );
}

function clusterLabel(i: number, k: number): string {
  if (k <= CLUSTER_NOMES.length) return CLUSTER_NOMES[i] ?? `Grupo ${i + 1}`;
  if (i === 0) return "Baixo";
  if (i === k - 1) return "Alto";
  return `Médio ${i}`;
}

function ClusterLegend({
  k,
  colors,
  selected,
  onSelect,
}: {
  k: number;
  colors: string[];
  selected: number | null;
  onSelect: (cluster: number | null) => void;
}) {
  return (
    <div className="legend">
      {colors.map((cor, i) => (
        <button
          type="button"
          key={i}
          className={`legend-item legend-btn${selected === i ? " active" : ""}${selected != null && selected !== i ? " dimmed" : ""}`}
          onClick={() => onSelect(selected === i ? null : i)}
          aria-pressed={selected === i}
        >
          <span className="legend-swatch" style={{ background: cor }} />
          {clusterLabel(i, k)}
        </button>
      ))}
    </div>
  );
}

function ErrorBox({ msg }: { msg: string }) {
  return <div className="note error">{msg}</div>;
}

export default function App() {
  const [states, setStates] = useState<StateMeta[]>([]);
  const [anosOpcoes, setAnosOpcoes] = useState<number[]>([]);
  const [anosLoading, setAnosLoading] = useState(true);
  const [ufSel, setUfSel] = useState<string>("BA");
  const [ano, setAno] = useState<number | null>(null);
  const [semanaIdx, setSemanaIdx] = useState(0);
  const [k, setK] = useState(4);
  const [anosError, setAnosError] = useState<string | null>(null);

  const [resumoSel, setResumoSel] = useState<ResumoAno[]>([]);
  const [resumoLoading, setResumoLoading] = useState(false);

  const [weekly, setWeekly] = useState<{ semana: number; casos: number }[]>([]);
  const [clusterByUf, setClusterByUf] = useState<
    Record<string, Record<string, Record<string, number>>>
  >({});
  const [weeklyCountsByUf, setWeeklyCountsByUf] = useState<
    Record<string, Record<string, Record<string, number>>>
  >({});
  const [clusterLoading, setClusterLoading] = useState(false);
  const [clusterCached, setClusterCached] = useState<boolean | null>(null);
  const [clusterError, setClusterError] = useState<string | null>(null);
  const [clusterFilter, setClusterFilter] = useState<number | null>(null);

  const anoAtual = ano ?? anosOpcoes[0] ?? new Date().getFullYear();

  const { geo, municipios, ufs, loading: regionLoading, error: regionError } =
    useRegionData(anoAtual);

  const semana = weekly[semanaIdx]?.semana ?? 1;
  const preparing = regionLoading || clusterLoading;
  const initLoading = anosLoading || (ano !== null && regionLoading && ufs.length === 0);

  useEffect(() => {
    setAnosLoading(true);
    fetchAnos()
      .then((r) => {
        setAnosOpcoes(r.anos);
        if (r.anos.length) setAno((prev) => prev ?? r.anos[0]);
      })
      .catch((e: Error) => setAnosError(e.message))
      .finally(() => setAnosLoading(false));
  }, []);

  useEffect(() => {
    if (ano === null || regionLoading) return;
    fetchStates(ano)
      .then((r) => setStates(r.states))
      .catch(() => {});
  }, [ano, regionLoading, ufs.length]);

  useEffect(() => {
    if (ano === null) return;
    setResumoLoading(true);
    if (regionLoading || ufSel === UF_TODOS) {
      setResumoSel([]);
      if (!regionLoading && ufSel === UF_TODOS) setResumoLoading(false);
      return;
    }
    fetchResumo(ufSel, ano)
      .then(setResumoSel)
      .catch(() => setResumoSel([]))
      .finally(() => setResumoLoading(false));
  }, [ufSel, ano, regionLoading]);

  const mapUfs = useMemo(
    () => (ufSel === UF_TODOS ? ufs : ufs.includes(ufSel) ? [ufSel] : []),
    [ufSel, ufs],
  );

  const geoMapa = useMemo((): FeatureCollection | null => {
    if (!geo) return null;
    if (ufSel === UF_TODOS) return geo;
    return {
      ...geo,
      features: geo.features.filter(
        (f) => (f.properties as { uf?: string })?.uf === ufSel,
      ),
    };
  }, [geo, ufSel]);

  useEffect(() => {
    if (ano === null || mapUfs.length === 0) {
      setWeekly([]);
      setClusterByUf({});
      setWeeklyCountsByUf({});
      return;
    }
    let cancelled = false;
    setClusterLoading(true);
    setClusterError(null);
    setClusterCached(null);
    fetchClusterRegion(mapUfs, ano, { k, min_casos: MIN_CASOS })
      .then((d) => {
        if (cancelled) return;
        setWeekly(d.weekly);
        setClusterByUf(d.clusterByUf);
        setWeeklyCountsByUf(d.weeklyCountsByUf);
        setClusterCached(d.cached);
        if (d.weekly.length) setSemanaIdx(Math.floor(d.weekly.length / 2));
      })
      .catch((e: Error) => {
        if (!cancelled) setClusterError(e.message);
      })
      .finally(() => {
        if (!cancelled) setClusterLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [mapUfs, ano, k]);

  useEffect(() => {
    setClusterFilter(null);
  }, [k, ufSel, anoAtual]);

  const clusterData = useMemo(() => {
    if (!weekly.length) return [];
    const key = String(semana);
    const pool =
      ufSel === UF_TODOS
        ? municipios
        : municipios.filter((m) => m.uf === ufSel);
    return pool.map((m) => {
      const uf = m.uf ?? "";
      const assign = clusterByUf[uf]?.[key] ?? {};
      const counts = weeklyCountsByUf[uf]?.[key] ?? {};
      return {
        ...m,
        cluster: assign[m.codarea] ?? 0,
        casosSemana: counts[m.codarea] ?? 0,
      };
    });
  }, [weekly.length, semana, municipios, clusterByUf, weeklyCountsByUf, ufSel]);

  const clusterCounts = useMemo(
    () =>
      Array.from({ length: k }, (_, i) => ({
        cluster: i,
        label: clusterLabel(i, k),
        municipios: clusterData.filter((m) => m.cluster === i).length,
      })),
    [clusterData, k],
  );

  const casosSemana = weekly[semanaIdx]?.casos ?? 0;

  const stateOptions = useMemo(
    () =>
      NORDESTE_UFS.map((uf) => {
        const meta = states.find((s) => s.uf === uf);
        return {
          uf,
          nome: meta?.nome ?? UF_NOMES[uf] ?? uf,
          ready: ufs.includes(uf) || meta?.ready === true,
        };
      }),
    [states, ufs],
  );

  const clusterColors = useMemo((): string[] => {
    const base: string[] = [...CLUSTER_COLORS];
    while (base.length < k) {
      const t = base.length / k;
      const r = Math.round(100 + 155 * t);
      base.push(`#${r.toString(16).padStart(2, "0")}6644`);
    }
    return base.slice(0, k);
  }, [k]);

  const volumeSectionLoading = anosLoading || regionLoading || resumoLoading;
  const clusterSectionLoading =
    anosLoading ||
    regionLoading ||
    clusterLoading ||
    (mapUfs.length > 0 && weekly.length === 0) ||
    (mapUfs.length > 0 && !geoMapa);

  const mapLabel =
    ufSel === UF_TODOS ? `todos (${ufs.length})` : `${ufSel} — ${UF_NOMES[ufSel] ?? ufSel}`;

  const semanaLabel =
    ufSel === UF_TODOS
      ? "Casos na região"
      : `Casos em ${UF_NOMES[ufSel] ?? ufSel}`;

  return (
    <div className="page">
      <header className="toolbar">
        <div className="toolbar-head">
          <h1>Dengue no Nordeste</h1>
          <p className="toolbar-sub">
            Notificações SINAN · malhas IBGE · cluster on-demand
          </p>
        </div>

        {anosLoading && (
          <SectionLoader label="Carregando anos disponíveis…" />
        )}

        <div className="toolbar-controls">
          <div className="control-group">
            <label htmlFor="uf-sel">Estado (mapa)</label>
            <select
              id="uf-sel"
              value={ufSel}
              onChange={(e) => setUfSel(e.target.value)}
              disabled={initLoading}
            >
              <option value={UF_TODOS}>Todos os estados</option>
              {stateOptions.map((s) => (
                <option key={s.uf} value={s.uf}>
                  {s.uf} — {s.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="control-group">
            <label htmlFor="ano">Ano</label>
            <select
              id="ano"
              value={anoAtual}
              onChange={(e) => setAno(Number(e.target.value))}
              disabled={anosLoading || !anosOpcoes.length}
            >
              {anosOpcoes.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
        </div>

        {(anosError || regionError) && (
          <div className="toolbar-errors">
            {anosError && <ErrorBox msg={anosError} />}
            {regionError && <ErrorBox msg={regionError} />}
          </div>
        )}
      </header>

      <main className="main">
        <Chapter
          title="Volume anual"
          loading={volumeSectionLoading}
          loadingLabel={
            ufSel === UF_TODOS
              ? "Selecione um estado específico…"
              : `Carregando histórico de ${UF_NOMES[ufSel] ?? ufSel}…`
          }
        >
          {ufSel === UF_TODOS ? (
            <p>
              Selecione um estado no seletor acima para ver o histórico multi-ano.
            </p>
          ) : (
            <>
              <p>Histórico de {UF_NOMES[ufSel] ?? ufSel}.</p>
              {resumoSel.length > 0 ? (
                <div className="viz">
                  <ChartAnos data={resumoSel} />
                  <p className="viz-caption">{ufSel}</p>
                </div>
              ) : (
                <ErrorBox msg={`Sem resumo para ${ufSel} em ${anoAtual}.`} />
              )}
            </>
          )}
        </Chapter>

        <Chapter
          title="Clusters semana a semana"
          loading={clusterSectionLoading}
          loadingLabel={
            regionLoading
              ? "Baixando malhas e extraindo SINAN…"
              : clusterLoading
                ? `Clusterizando ${mapUfs.length} estado(s) · k=${k}…`
                : "Montando visualizações…"
          }
        >
          <p>
            K-means em log(casos) — {mapLabel} · {anoAtual}.
            {ufSel === UF_TODOS
              ? ` Soma de ${mapUfs.length} estado(s).`
              : ` ${UF_NOMES[ufSel] ?? ufSel}.`}
            {!preparing && clusterCached === true && (
              <span className="params-cached"> · do cache</span>
            )}
            {!preparing && clusterCached === false && (
              <span className="params-live"> · recém-calculado</span>
            )}
          </p>
          <div className="chapter-controls">
            <div className="control-group">
              <label htmlFor="k">Grupos (k)</label>
              <select
                id="k"
                value={k}
                onChange={(e) => setK(Number(e.target.value))}
                disabled={preparing}
              >
                {[2, 3, 4, 5, 6].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <ClusterLegend
            k={k}
            colors={clusterColors}
            selected={clusterFilter}
            onSelect={setClusterFilter}
          />
          {clusterError && <ErrorBox msg={clusterError} />}
          {geoMapa && geoMapa.features.length > 0 && clusterData.length > 0 && (
            <div className="viz">
              <ChoroplethMap
                geo={geoMapa}
                counts={clusterData}
                valueKey="cluster"
                clusterColors={clusterColors}
                clusterFilter={clusterFilter}
                mapKey={`${ufSel}-${anoAtual}-${semana}-k${k}-f${clusterFilter ?? "all"}`}
              />
              <p className="viz-caption">
                Semana {semana}
                {clusterFilter != null && (
                  <> · filtrando <strong>{clusterLabel(clusterFilter, k)}</strong></>
                )}
                {" · "}
                {clusterFilter != null
                  ? `${clusterData.filter((m) => m.cluster === clusterFilter).length} municípios`
                  : `${clusterData.length} municípios`}
                {ufSel === UF_TODOS ? ` · ${mapUfs.length} estados` : ` · ${ufSel}`}
              </p>
            </div>
          )}
          {weekly.length > 0 && clusterCounts.some((row) => row.municipios > 0) && (
            <div className="viz">
              <p className="viz-lead">
                Municípios por cluster — semana {semana} · {mapLabel}.
              </p>
              <ChartClusterCounts
                data={clusterCounts}
                colors={clusterColors}
                activeCluster={clusterFilter}
                onClusterSelect={setClusterFilter}
              />
              <p className="viz-caption">
                Clique numa barra ou na legenda para filtrar o mapa.
              </p>
            </div>
          )}
          {weekly.length > 0 && (
            <div className="viz">
              <p className="viz-lead">
                Casos por semana — {semanaLabel.toLowerCase()} em {anoAtual}.
              </p>
              <ChartSemanas
                data={weekly}
                seriesLabel={semanaLabel}
                activeSemana={semana}
                onSemanaSelect={setSemanaIdx}
              />
            </div>
          )}
          {weekly.length > 0 && (
            <div className="semana-bridge">
              <div className="control-group">
                <label htmlFor="sem-slider">
                  Semana {semana} · {fmt(casosSemana)} casos
                  {ufSel === UF_TODOS ? " na região" : ` em ${ufSel}`}
                </label>
                <input
                  id="sem-slider"
                  type="range"
                  min={0}
                  max={Math.max(0, weekly.length - 1)}
                  value={semanaIdx}
                  onChange={(e) => setSemanaIdx(Number(e.target.value))}
                  disabled={preparing}
                />
              </div>
              <p className="semana-bridge-hint">
                Arraste o controle ou clique no gráfico — o mapa acima acompanha a semana
                selecionada.
              </p>
            </div>
          )}
        </Chapter>
      </main>
    </div>
  );
}
