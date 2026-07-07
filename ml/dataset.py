"""Carrega parquet agregado e constrói features em memória."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.feature_engineering import build_features
from ml.paths import region_parquet_path
from ml.preprocess import YEAR_COL
from ml.regions import RegionSpec, resolve_region


def load_region_raw(region: RegionSpec | str, year: int | None = None) -> pd.DataFrame:
    spec = resolve_region(region) if isinstance(region, str) else region
    path = region_parquet_path(spec.slug)
    if not path.exists():
        raise FileNotFoundError(
            f"Parquet ausente: {path}. Rode: uv run ia-iv --data --region {spec.slug}"
        )
    df = pd.read_parquet(path)
    if year is not None:
        if YEAR_COL not in df.columns:
            raise KeyError(f"Coluna {YEAR_COL!r} ausente em {path}")
        df = df.loc[df[YEAR_COL] == year].copy()
    return df


def build_features_panel(
    region: RegionSpec | str,
    year: int,
    version: str,
) -> pd.DataFrame:
    """Painel município×semana com features (sem gravar parquet intermediário)."""
    spec = resolve_region(region) if isinstance(region, str) else region
    raw = load_region_raw(spec, year)
    return build_features(raw, spec, year, version)


def load_or_build_features(
    region: RegionSpec | str,
    year: int,
    version: str,
    *,
    force: bool = False,
) -> tuple[pd.DataFrame, Path]:
    """Compat com notebooks/CLI: features sempre em memória; ``force`` ignorado."""
    _ = force
    spec = resolve_region(region) if isinstance(region, str) else region
    panel = build_features_panel(spec, year, version)
    return panel, region_parquet_path(spec.slug)


load_raw_parquet = load_region_raw
