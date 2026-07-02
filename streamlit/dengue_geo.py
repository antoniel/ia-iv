"""Dashboard Streamlit — mapas e clusters de dengue (BA)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st
from branca.colormap import linear
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parent.parent
UF = "ba"
GEO_PATH = ROOT / "data/raw/geo/ba_municipios.geojson"
DATA_DIR = ROOT / "data/processed" / UF / "raw"

CLUSTER_COLORS = ["#1b7837", "#2166ac", "#762a83", "#b2182b"]
CLUSTER_NOMES = ["Baixo", "Médio-", "Médio+", "Alto"]


def ordenar_clusters_por_intensidade(
    labels: np.ndarray, valores: np.ndarray
) -> np.ndarray:
    media = pd.DataFrame({"lbl": labels, "v": valores}).groupby("lbl")["v"].mean().sort_values()
    old_to_new = {int(old): new for new, old in enumerate(media.index)}
    return np.array([old_to_new[int(l)] for l in labels])


@st.cache_data
def anos_disponiveis() -> list[int]:
    anos = []
    for p in sorted(DATA_DIR.glob(f"DENG{UF.upper()}*.csv")):
        anos.append(2000 + int(p.stem[-2:]))
    return anos


@st.cache_data
def load_ibge_nomes() -> pd.DataFrame:
    data = requests.get(
        "https://servicodados.ibge.gov.br/api/v1/localidades/estados/29/municipios",
        timeout=30,
    ).json()
    df = pd.DataFrame(data).rename(columns={"id": "codarea", "nome": "municipio"})
    df["codarea"] = df["codarea"].astype(str)
    return df[["codarea", "municipio"]]


@st.cache_data
def load_geo() -> dict:
    with GEO_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def id_to_codarea_map(_geo_json: str) -> dict[int, str]:
    geo = json.loads(_geo_json)
    out: dict[int, str] = {}
    for feat in geo["features"]:
        ca = str(feat["properties"]["codarea"])
        out[int(ca) // 10] = ca
    return out


@st.cache_data
def load_counts_ano(ano: int) -> tuple[pd.DataFrame, str, int]:
    path = DATA_DIR / f"DENG{UF.upper()}{str(ano)[-2:]}.csv"
    df = pd.read_csv(
        path,
        usecols=["ID_MUNICIP", "DT_NOTIFIC"],
        parse_dates=["DT_NOTIFIC"],
        low_memory=False,
    )
    counts = (
        df.groupby("ID_MUNICIP", as_index=False)
        .size()
        .rename(columns={"size": "notificacoes"})
    )
    id_map = id_to_codarea_map(json.dumps(load_geo()))
    counts["codarea"] = counts["ID_MUNICIP"].map(id_map)
    counts = counts.merge(load_ibge_nomes(), on="codarea", how="left")
    counts["municipio"] = counts["municipio"].fillna(counts["codarea"])
    periodo = f"{df['DT_NOTIFIC'].min():%d/%m/%Y} — {df['DT_NOTIFIC'].max():%d/%m/%Y}"
    return counts, periodo, len(df)


@st.cache_data
def load_matriz_semanal(ano: int, min_casos: int) -> tuple[pd.DataFrame, dict[int, int]]:
    path = DATA_DIR / f"DENG{UF.upper()}{str(ano)[-2:]}.csv"
    df = pd.read_csv(path, usecols=["ID_MUNICIP", "SEM_NOT"], low_memory=False)
    mat = df.groupby(["ID_MUNICIP", "SEM_NOT"]).size().unstack(fill_value=0).sort_index(axis=1)
    mat = mat[mat.sum(axis=1) >= min_casos]
    sem_map = {int(str(s)[-2:]): s for s in mat.columns.astype(int)}
    return mat, sem_map


@st.cache_data
def clusters_semanais(ano: int, k: int, min_casos: int) -> pd.DataFrame:
    mat, sem_map = load_matriz_semanal(ano, min_casos)
    assign: dict[int, pd.Series] = {}
    for num_sem, col in sem_map.items():
        casos = mat[col].values
        X = casos.astype(float).reshape(-1, 1)
        raw = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X)
        assign[num_sem] = pd.Series(
            ordenar_clusters_por_intensidade(raw, casos), index=mat.index
        )
    return pd.DataFrame(assign)


def mapa_notificacoes(counts: pd.DataFrame, ano: int) -> folium.Map:
    geo = copy.deepcopy(load_geo())
    lookup = counts.set_index("codarea")[["notificacoes", "municipio"]].to_dict("index")
    for feat in geo["features"]:
        ca = str(feat["properties"]["codarea"])
        info = lookup.get(ca, {"notificacoes": 0, "municipio": ca})
        feat["properties"]["notificacoes"] = int(info["notificacoes"])
        feat["properties"]["municipio"] = info["municipio"]

    vmax = max(int(counts["notificacoes"].max()), 1)
    m = folium.Map(location=[-12.5, -41.7], zoom_start=6, tiles="OpenStreetMap")
    cmap = linear.YlOrRd_09.scale(0, vmax)
    cmap.caption = f"Notificações — BA {ano}"
    folium.GeoJson(
        geo,
        style_function=lambda feat, c=cmap: {
            "fillColor": c(feat["properties"]["notificacoes"]),
            "color": "#333",
            "weight": 0.7,
            "fillOpacity": 0.85,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["municipio", "notificacoes"],
            aliases=["Município", "Notificações"],
        ),
    ).add_to(m)
    cmap.add_to(m)
    return m


def mapa_cluster_semana(
    assign_df: pd.DataFrame,
    mat: pd.DataFrame,
    sem_map: dict[int, int],
    num_sem: int,
    nome_map: dict[int, str],
    k: int,
) -> folium.Map:
    col = sem_map[num_sem]
    lookup = assign_df[num_sem].to_dict()
    colors = CLUSTER_COLORS[:k]
    nomes = CLUSTER_NOMES[:k]
    geo = copy.deepcopy(load_geo())

    for feat in geo["features"]:
        ca = str(feat["properties"]["codarea"])
        id6 = int(ca) // 10
        c = int(lookup.get(id6, -1))
        feat["properties"]["municipio"] = nome_map.get(id6, ca)
        feat["properties"]["casos"] = int(mat.at[id6, col]) if id6 in mat.index else 0
        feat["properties"]["nivel"] = nomes[c] if c >= 0 else "—"

    def style(feat: dict) -> dict:
        c = int(lookup.get(int(str(feat["properties"]["codarea"])) // 10, -1))
        if c < 0:
            return {"fillColor": "#bdbdbd", "color": "#666", "weight": 0.8, "fillOpacity": 0.45}
        return {"fillColor": colors[c], "color": "#111", "weight": 1.2, "fillOpacity": 0.92}

    m = folium.Map(location=[-12.5, -41.7], zoom_start=6, tiles="OpenStreetMap")
    folium.GeoJson(
        geo,
        style_function=style,
        tooltip=folium.GeoJsonTooltip(
            fields=["municipio", "casos", "nivel"],
            aliases=["Município", "Casos", "Intensidade"],
        ),
    ).add_to(m)
    return m


def plot_diagnostico_semana(
    mat: pd.DataFrame,
    assign_df: pd.DataFrame,
    sem_map: dict[int, int],
    num_sem: int,
    k: int,
) -> tuple[plt.Figure, float]:
    col = sem_map[num_sem]
    casos = mat[col].values
    clusters = assign_df[num_sem].values
    sil = silhouette_score(casos.astype(float).reshape(-1, 1), clusters)
    colors = CLUSTER_COLORS[:k]
    nomes = CLUSTER_NOMES[:k]
    rng = np.random.default_rng(42)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    plot_df = pd.DataFrame({"casos": casos, "cluster": clusters})

    for c in range(k):
        sub = plot_df.loc[plot_df["cluster"] == c, "casos"]
        axes[0].scatter(
            rng.normal(c, 0.07, len(sub)),
            sub,
            alpha=0.5,
            s=22,
            c=colors[c],
            edgecolors="#222",
            linewidths=0.25,
            label=f"{nomes[c]} (n={len(sub)})",
        )
    axes[0].set_xticks(range(k))
    axes[0].set_xticklabels(nomes)
    axes[0].set_yscale("symlog", linthresh=1)
    axes[0].set_ylabel("Casos na semana")
    axes[0].legend(fontsize=7)
    axes[0].grid(axis="y", alpha=0.3)

    agg = plot_df.groupby("cluster")["casos"].agg(["count", "mean"])
    axes[1].bar(range(k), agg["count"].reindex(range(k), fill_value=0), color=colors, edgecolor="#111")
    axes[1].set_xticks(range(k))
    axes[1].set_xticklabels(nomes)
    ax_r = axes[1].twinx()
    ax_r.plot(range(k), agg["mean"].reindex(range(k), fill_value=0), "D--k", ms=6)
    axes[1].set_ylabel("Municípios")
    ax_r.set_ylabel("Média casos")

    qualidade = "boa" if sil >= 0.25 else "média" if sil >= 0.1 else "fraca"
    fig.suptitle(f"Semana {num_sem:02d} — silhouette {sil:.2f} ({qualidade})", fontsize=10, y=1.02)
    plt.tight_layout()
    return fig, sil


def main() -> None:
    st.set_page_config(page_title="Dengue BA — Geo", layout="wide")
    st.title("Dengue SINAN — Bahia")
    st.caption("Mapas e clusterização por município (local de notificação)")

    anos = anos_disponiveis()
    if not anos:
        st.error(f"Nenhum CSV em {DATA_DIR}")
        st.stop()

    tab_mapa, tab_cluster = st.tabs(["Mapa anual", "Cluster semanal"])

    with tab_mapa:
        ano = st.selectbox("Ano", anos, index=len(anos) - 1, key="ano_mapa")
        counts, periodo, total = load_counts_ano(ano)
        st.metric("Notificações", f"{total:,}".replace(",", "."))
        st.caption(f"Período: {periodo} · {counts['ID_MUNICIP'].nunique()} municípios")
        st_folium(mapa_notificacoes(counts, ano), width=None, height=520, returned_objects=[])

        with st.expander("Top 15 municípios"):
            st.dataframe(
                counts.nlargest(15, "notificacoes")[["municipio", "notificacoes"]],
                hide_index=True,
            )

    with tab_cluster:
        c1, c2, c3 = st.columns(3)
        ano_c = c1.selectbox("Ano", anos, index=len(anos) - 1, key="ano_cluster")
        k = c2.select_slider("Clusters (k)", options=[2, 3, 4, 5, 6], value=4)
        min_casos = c3.number_input("Mín. casos/ano", min_value=1, value=30, step=10)

        mat, sem_map = load_matriz_semanal(ano_c, min_casos)
        assign_df = clusters_semanais(ano_c, k, min_casos)
        semanas = sorted(assign_df.columns.tolist())
        num_sem = st.slider("Semana epidemiológica", int(min(semanas)), int(max(semanas)), int(semanas[-1]))

        id_map = id_to_codarea_map(json.dumps(load_geo()))
        ibge = load_ibge_nomes()
        meta = pd.DataFrame({"ID_MUNICIP": mat.index})
        meta["codarea"] = meta["ID_MUNICIP"].map(id_map)
        meta = meta.merge(ibge, on="codarea", how="left")
        nome_map = meta.set_index("ID_MUNICIP")["municipio"].to_dict()

        col = sem_map[num_sem]
        casos_sem = int(mat[col].sum())
        mudou = assign_df.diff(axis=1).ne(0).iloc[:, 1:]
        pct = mudou[num_sem].mean() * 100 if num_sem in mudou.columns else float("nan")

        fig, sil = plot_diagnostico_semana(mat, assign_df, sem_map, num_sem, k)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Casos na semana", f"{casos_sem:,}".replace(",", "."))
        m2.metric("Silhouette", f"{sil:.2f}")
        m3.metric("% mudou vs sem. ant.", f"{pct:.1f}%" if pct == pct else "—")
        m4.metric("Municípios", len(mat))

        st.caption("Cores fixas: verde = baixo · azul · roxo · vermelho = alto")
        left, right = st.columns([3, 2])
        with left:
            st_folium(
                mapa_cluster_semana(assign_df, mat, sem_map, num_sem, nome_map, k),
                width=None,
                height=480,
                returned_objects=[],
            )
        with right:
            st.pyplot(fig)
            plt.close(fig)


if __name__ == "__main__":
    main()
