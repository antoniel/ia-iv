"""Validação interpretável dos clusters."""

from __future__ import annotations

import pandas as pd

from ml.cluster import ClusterResult
from ml.columns import Col


def transition_matrix(panel: pd.DataFrame, labels: list[int] | pd.Series) -> pd.DataFrame:
    """Transições semana t → t+1, dentro de cada município."""
    df = panel[[Col.ID_MUNICIP, Col.SEM_NOT]].copy()
    df["cluster"] = list(labels)
    df = df.sort_values([Col.ID_MUNICIP, Col.SEM_NOT])

    pairs: list[pd.DataFrame] = []
    for _, grp in df.groupby(Col.ID_MUNICIP):
        g = grp.copy()
        g["cluster_next"] = g["cluster"].shift(-1)
        pairs.append(g.dropna(subset=["cluster_next"]))

    if not pairs:
        return pd.DataFrame()

    all_pairs = pd.concat(pairs, ignore_index=True)
    trans = pd.crosstab(all_pairs["cluster"], all_pairs["cluster_next"], normalize="index")
    trans.index.name = "de"
    trans.columns.name = "para"
    return trans.round(3)


def summarize_result(panel: pd.DataFrame, result: ClusterResult) -> dict:
    labeled = panel.copy()
    labeled["cluster"] = result.labels
    trans = transition_matrix(panel, result.labels)
    return {
        "cluster_sizes": labeled["cluster"].value_counts().sort_index().to_dict(),
        "cluster_means": result.cluster_means.to_dict(orient="index"),
        "transitions": trans.to_dict() if not trans.empty else {},
        "n_municipios": int(panel[Col.ID_MUNICIP].nunique()),
        "n_semanas": int(panel[Col.SEM_NOT].nunique()),
    }
