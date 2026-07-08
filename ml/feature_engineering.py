"""Constrói painel município × semana com features epidemiológicas."""

from __future__ import annotations

import logging

import pandas as pd

from ml.columns import Col, Feat, resolve_features
from ml.config import DEFAULT_MIN_CASOS_ANUAL, REFERENCE_POP_YEAR
from ml.reference import load_population
from ml.regions import RegionSpec

log = logging.getLogger(__name__)

MOVING_WINDOW = 3


def _semana_epidemiologica(sem_not: pd.Series) -> pd.Series:
    return sem_not.astype(str).str[-2:].astype(int)


def weekly_panel(
    raw: pd.DataFrame,
    region: RegionSpec,
    year: int,
    *,
    min_casos_anual: int = DEFAULT_MIN_CASOS_ANUAL,
) -> pd.DataFrame:
    """Agrega município × semana; completa semanas faltantes com 0 casos."""
    pop_df = load_population(region.slug, region.ufs, REFERENCE_POP_YEAR)
    pop_map = pop_df.set_index("id_municip")["populacao"]
    dens_map = pop_df.set_index("id_municip")[Feat.DENSIDADE_KM2]

    counts = (
        raw.groupby([Col.ID_MUNICIP, Col.SEM_NOT], as_index=False)
        .size()
        .rename(columns={"size": Feat.CASOS})
    )
    counts[Col.ID_MUNICIP] = counts[Col.ID_MUNICIP].astype(int)

    anual = counts.groupby(Col.ID_MUNICIP)[Feat.CASOS].sum()
    eligible = anual[anual >= min_casos_anual].index
    counts = counts[counts[Col.ID_MUNICIP].isin(eligible)]

    semanas = sorted(counts[Col.SEM_NOT].unique())
    log.info(
        "[%s %d] elegíveis: %d municípios (≥%d casos/ano), %d semanas",
        region.slug,
        year,
        len(eligible),
        min_casos_anual,
        len(semanas),
    )

    frames: list[pd.DataFrame] = []
    for id6 in eligible:
        sub = counts[counts[Col.ID_MUNICIP] == id6].set_index(Col.SEM_NOT)
        full = sub.reindex(semanas).fillna({Feat.CASOS: 0}).astype({Feat.CASOS: int})
        full[Col.ID_MUNICIP] = id6
        full = full.reset_index()
        frames.append(full)

    panel = pd.concat(frames, ignore_index=True)
    panel[Feat.SEMANA_EP] = _semana_epidemiologica(panel[Col.SEM_NOT])
    panel[Feat.POPULACAO] = panel[Col.ID_MUNICIP].map(pop_map)
    panel[Feat.DENSIDADE_KM2] = panel[Col.ID_MUNICIP].map(dens_map)
    panel = panel.dropna(subset=[Feat.POPULACAO, Feat.DENSIDADE_KM2])
    panel = panel.sort_values([Col.ID_MUNICIP, Col.SEM_NOT]).reset_index(drop=True)
    return panel


def add_temporal_features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out[Feat.INCIDENCIA_100K] = out[Feat.CASOS] / out[Feat.POPULACAO] * 100_000

    g = out.groupby(Col.ID_MUNICIP, group_keys=False)
    out[Feat.MEDIA_MOVEL_3] = g[Feat.INCIDENCIA_100K].transform(
        lambda s: s.rolling(MOVING_WINDOW, min_periods=1).mean()
    )
    out[Feat.CRESCIMENTO] = g[Feat.INCIDENCIA_100K].transform(lambda s: s.diff().fillna(0.0))
    out[Feat.ACELERACAO] = g[Feat.CRESCIMENTO].transform(lambda s: s.diff().fillna(0.0))
    return out


def build_features(
    raw: pd.DataFrame,
    region: RegionSpec,
    year: int,
    version: str,
    *,
    min_casos_anual: int = DEFAULT_MIN_CASOS_ANUAL,
) -> pd.DataFrame:
    features = resolve_features(version)
    panel = weekly_panel(raw, region, year, min_casos_anual=min_casos_anual)
    panel = add_temporal_features(panel)

    # CASOS fica no painel para interpretação/ordenação, mesmo se não entrar no fit
    keep = list(dict.fromkeys([Col.ID_MUNICIP, Col.SEM_NOT, Feat.SEMANA_EP, Feat.CASOS, *features]))
    out = panel[keep].copy()
    log.info(
        "[%s %d %s] painel: %d linhas (município×semana), %d features",
        region.slug,
        year,
        version,
        len(out),
        len(features),
    )
    return out
