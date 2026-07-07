"""Caminhos do pipeline ML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml.config import DATA_ML, DATA_PROCESSED, DATA_RAW, ROOT


def raw_csv_path(year: int) -> Path:
    yy = str(year)[-2:]
    return DATA_RAW / f"DENGBR{yy}.csv"


def processed_uf_csv_path(uf: str, year: int) -> Path:
    yy = str(year)[-2:]
    return DATA_PROCESSED / uf.lower() / "raw" / f"DENG{uf.upper()}{yy}.csv"


def region_dir(slug: str) -> Path:
    return DATA_ML / slug


def region_parquet_path(slug: str) -> Path:
    """Parquet agregado: todas as notificações da região (coluna ``year``)."""
    return region_dir(slug) / "dengue.parquet"


def region_manifest_path(slug: str) -> Path:
    return region_dir(slug) / "dengue.manifest.json"


def region_population_path(slug: str) -> Path:
    """Referência municipal única (população, área, densidade)."""
    return region_dir(slug) / "populacao.parquet"


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
