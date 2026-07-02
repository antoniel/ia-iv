from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from backend.config import CLUSTER_CACHE, DEFAULT_K, DEFAULT_MIN_CASOS
from backend.data import raw_csv_path
from backend.geo import codarea_maps, load_geo

log = logging.getLogger(__name__)


def ordenar_clusters(labels: np.ndarray, valores: np.ndarray) -> np.ndarray:
    media = pd.DataFrame({"lbl": labels, "v": valores}).groupby("lbl")["v"].mean().sort_values()
    mapping = {int(old): new for new, old in enumerate(media.index)}
    return np.array([mapping[int(l)] for l in labels])


def cluster_cache_path(uf: str, ano: int, k: int, min_casos: int) -> Path:
    return CLUSTER_CACHE / uf.lower() / f"{ano}_k{k}_min{min_casos}_weekly_raw.json"


def compute_weekly_clusters(
    uf: str,
    ano: int,
    *,
    k: int = DEFAULT_K,
    min_casos: int = DEFAULT_MIN_CASOS,
) -> dict:
    csv_path = raw_csv_path(uf, ano)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV estadual ausente: {csv_path}")

    geo = load_geo(uf)
    id_to_cod, _ = codarea_maps(geo)

    log.info(
        "[%s %d] clusterizando (k=%d, min_casos=%d)…",
        uf.upper(),
        ano,
        k,
        min_casos,
    )
    df = pd.read_csv(csv_path, usecols=["ID_MUNICIP", "SEM_NOT"], low_memory=False)
    mat_all = df.groupby(["ID_MUNICIP", "SEM_NOT"]).size().unstack(fill_value=0).sort_index(axis=1)
    if mat_all.empty:
        return {
            "weekly": [],
            "assignments": {},
            "weeklyCounts": {},
            "params": {"k": k, "min_casos": min_casos},
        }

    eligible = mat_all.sum(axis=1) >= min_casos
    mat_elig = mat_all.loc[eligible]

    sem_map = {int(str(s)[-2:]): int(s) for s in mat_all.columns.astype(int)}
    weekly: list[dict] = []
    assignments: dict[str, dict[str, int]] = {}
    weekly_counts: dict[str, dict[str, int]] = {}

    sem_items = sorted(sem_map.items())
    n_sem = len(sem_items)
    for i, (num, col) in enumerate(sem_items, 1):
        casos_col_all = mat_all[col]
        weekly.append({"semana": num, "casos": int(casos_col_all.sum())})

        week_assign: dict[str, int] = {}
        week_counts: dict[str, int] = {}

        for id6 in mat_all.index.astype(int):
            cod = id_to_cod.get(id6)
            if cod is None:
                continue
            week_counts[cod] = int(casos_col_all[id6])

        if not mat_elig.empty:
            casos_elig = mat_elig[col]
            X = casos_elig.values.astype(float).reshape(-1, 1)
            raw_labels = KMeans(k, random_state=42, n_init=10).fit_predict(X)
            labels = ordenar_clusters(raw_labels, casos_elig.values)
            elig_assign = {
                id_to_cod[int(id6)]: int(cl)
                for id6, cl in zip(mat_elig.index.astype(int), labels)
                if int(id6) in id_to_cod
            }
            for id6 in mat_all.index.astype(int):
                cod = id_to_cod.get(id6)
                if cod is None:
                    continue
                week_assign[cod] = elig_assign.get(cod, 0)
        else:
            for id6 in mat_all.index.astype(int):
                cod = id_to_cod.get(id6)
                if cod is not None:
                    week_assign[cod] = 0

        assignments[str(num)] = week_assign
        weekly_counts[str(num)] = week_counts
        if i == 1 or i == n_sem or i % 10 == 0:
            log.info("[%s %d] cluster semana %d/%d (sem %d)", uf.upper(), ano, i, n_sem, num)

    log.info("[%s %d] cluster pronto — %d semanas", uf.upper(), ano, len(weekly))
    return {
        "weekly": weekly,
        "assignments": assignments,
        "weeklyCounts": weekly_counts,
        "params": {"k": k, "min_casos": min_casos, "uf": uf.upper(), "ano": ano},
    }


def get_weekly_clusters(
    uf: str,
    ano: int,
    *,
    k: int = DEFAULT_K,
    min_casos: int = DEFAULT_MIN_CASOS,
    force: bool = False,
) -> tuple[dict, bool]:
    """Retorna (payload, cache_hit)."""
    path = cluster_cache_path(uf, ano, k, min_casos)
    if path.exists() and not force:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("weeklyCounts"):
            log.info("[%s %d] cluster cache HIT → %s", uf.upper(), ano, path)
            return payload, True
        log.info("[%s %d] cluster cache stale (sem weeklyCounts) — recomputando", uf.upper(), ano)

    payload = compute_weekly_clusters(uf, ano, k=k, min_casos=min_casos)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    log.info("[%s %d] cluster cache MISS — salvo → %s", uf.upper(), ano, path)
    return payload, False
