"""Clusterização semanal e métricas internas."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from ml.columns import Col, Feat, resolve_features


@dataclass
class ClusterResult:
    labels: np.ndarray
    inertia: float
    metrics: dict[str, float | None]
    cluster_means: pd.DataFrame
    n_samples: int
    n_features: int


def _order_clusters(labels: np.ndarray, values: np.ndarray) -> np.ndarray:
    order = (
        pd.DataFrame({"lbl": labels, "v": values})
        .groupby("lbl")["v"]
        .mean()
        .sort_values()
        .index.tolist()
    )
    mapping = {int(old): new for new, old in enumerate(order)}
    return np.array([mapping[int(l)] for l in labels])


def run_kmeans(
    panel: pd.DataFrame,
    feature_version: str,
    *,
    k: int,
    random_state: int = 42,
) -> ClusterResult:
    features = resolve_features(feature_version)
    X_raw = panel[list(features)].astype(float).values
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    if len(panel) < k:
        raise ValueError(f"Poucas observações ({len(panel)}) para k={k}")

    model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    raw_labels = model.fit_predict(X)

    sort_key = panel[Feat.CASOS].values if Feat.CASOS in panel.columns else X_raw[:, 0]
    labels = _order_clusters(raw_labels, sort_key)

    metrics: dict[str, float | None] = {
        "inertia": float(model.inertia_),
        "silhouette": None,
        "davies_bouldin": None,
        "calinski_harabasz": None,
    }
    if len(np.unique(labels)) > 1 and len(panel) > k:
        metrics["silhouette"] = float(silhouette_score(X, labels))
        metrics["davies_bouldin"] = float(davies_bouldin_score(X, labels))
        metrics["calinski_harabasz"] = float(calinski_harabasz_score(X, labels))

    labeled = panel.copy()
    labeled["cluster"] = labels
    mean_cols = list(dict.fromkeys([*features, Feat.CASOS]))
    mean_cols = [c for c in mean_cols if c in labeled.columns]
    cluster_means = labeled.groupby("cluster")[mean_cols].mean().round(3)

    return ClusterResult(
        labels=labels,
        inertia=float(model.inertia_),
        metrics=metrics,
        cluster_means=cluster_means,
        n_samples=len(panel),
        n_features=len(features),
    )
