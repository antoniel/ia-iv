"""Extrai notificações SINAN por UF e grava um único Parquet agregado."""

from __future__ import annotations

import logging
import time

import pandas as pd

from ml.columns import Col, REQUIRED_RAW_COLS
from ml.config import DEFAULT_CHUNKSIZE, DEFAULT_YEARS, ROOT
from ml.paths import (
    processed_uf_csv_path,
    raw_csv_path,
    region_manifest_path,
    region_parquet_path,
    write_manifest,
)
from ml.regions import RegionSpec

log = logging.getLogger(__name__)

YEAR_COL = "year"


def _validate_header(csv_path) -> None:
    header = pd.read_csv(csv_path, nrows=0).columns.tolist()
    missing = [c for c in REQUIRED_RAW_COLS if c not in header]
    if missing:
        raise RuntimeError(f"{csv_path.name}: colunas ausentes {missing}")


def _read_year_csv(region: RegionSpec, year: int, *, chunksize: int) -> pd.DataFrame:
    processed = processed_uf_csv_path(region.uf, year)
    usecols = list({*REQUIRED_RAW_COLS, Col.ID_AGRAVO})

    if processed.exists():
        log.info("[%s %d] CSV estadual → %s", region.slug, year, processed.name)
        df = pd.read_csv(processed, usecols=usecols, low_memory=False)
        return df

    inp = raw_csv_path(year)
    if not inp.exists():
        raise FileNotFoundError(
            f"CSV ausente: {inp} e {processed}. "
            f"Rode: uv run ia-iv --data --download --years {year}"
        )
    _validate_header(inp)
    log.info("[%s %d] extraindo de %s (UF=%d)…", region.slug, year, inp.name, region.uf_code)
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(inp, usecols=usecols, chunksize=chunksize, low_memory=False):
        filtered = chunk.loc[chunk[Col.SG_UF_NOT] == region.uf_code]
        if not filtered.empty:
            chunks.append(filtered)
    if not chunks:
        return pd.DataFrame(columns=[*usecols, YEAR_COL])
    return pd.concat(chunks, ignore_index=True)


def build_region_parquet(
    region: RegionSpec,
    years: list[int] | None = None,
    *,
    chunksize: int = DEFAULT_CHUNKSIZE,
    force: bool = False,
) -> Path:
    """Um parquet por região com todos os anos (``data/ml/{slug}/dengue.parquet``)."""
    years = sorted(set(years or DEFAULT_YEARS))
    out = region_parquet_path(region.slug)
    manifest = region_manifest_path(region.slug)

    if out.exists() and not force:
        log.info("[%s] parquet agregado já existe → %s", region.slug, out)
        return out

    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    frames: list[pd.DataFrame] = []
    registros_por_ano: dict[str, int] = {}
    municipios_por_ano: dict[str, int] = {}

    for year in years:
        df = _read_year_csv(region, year, chunksize=chunksize)
        df = df.copy()
        df[YEAR_COL] = year
        frames.append(df)
        registros_por_ano[str(year)] = int(len(df))
        municipios_por_ano[str(year)] = int(df[Col.ID_MUNICIP].nunique()) if len(df) else 0
        log.info(
            "[%s %d] %s notificações, %d municípios",
            region.slug,
            year,
            f"{len(df):,}".replace(",", "."),
            municipios_por_ano[str(year)],
        )

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    combined.to_parquet(out, index=False, engine="pyarrow")

    elapsed = time.perf_counter() - t0
    write_manifest(
        manifest,
        {
            "region": region.name,
            "slug": region.slug,
            "uf": region.uf,
            "uf_code": region.uf_code,
            "years": years,
            "registros_por_ano": registros_por_ano,
            "municipios_por_ano": municipios_por_ano,
            "registros_total": int(len(combined)),
            "output_parquet": str(out.relative_to(ROOT)),
            "elapsed_seconds": round(elapsed, 2),
        },
    )

    log.info(
        "[%s] agregado: %s notificações (%d anos) → %s",
        region.slug,
        f"{len(combined):,}".replace(",", "."),
        len(years),
        out,
    )
    return out


def extract_region_parquet(region: RegionSpec, year: int, **kwargs) -> Path:
    """Compat: garante parquet agregado incluindo ``year``."""
    years = kwargs.pop("years", None) or DEFAULT_YEARS
    if year not in years:
        years = sorted(set([*years, year]))
    return build_region_parquet(region, years, **kwargs)
