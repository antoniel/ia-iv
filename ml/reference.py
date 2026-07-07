"""Tabelas auxiliares: população, área e densidade municipal (IBGE)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import requests

from ml.config import ROOT, UF_IBGE
from ml.paths import region_population_path, write_manifest

log = logging.getLogger(__name__)

IBGE_MUNICIPIOS_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf_code}/municipios"
)
IBGE_POP_URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/{year}/variaveis/9324"
)
IBGE_AREA_URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/6318"
)


def _ibge_get(url: str, params: dict, *, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=60)
            if not resp.ok:
                continue
            return resp.json()
        except requests.RequestException:
            if attempt == retries - 1:
                return None
            time.sleep(1.0)
    return None


def _fetch_population(id7: int, year: int) -> float | None:
    data = _ibge_get(IBGE_POP_URL.format(year=year), {"localidades": f"N6[{id7}]"})
    if not data:
        return None
    serie = data[0]["resultados"][0]["series"][0]["serie"]
    val = serie.get(str(year))
    return float(val) if val is not None else None


def _fetch_area_km2(id7: int) -> float | None:
    """Área territorial km² (Censo 2022, tabela 4714, variável 6318)."""
    data = _ibge_get(IBGE_AREA_URL, {"localidades": f"N6[{id7}]"})
    if not data:
        return None
    serie = data[0]["resultados"][0]["series"][0]["serie"]
    val = serie.get("2022")
    return float(val) if val is not None else None


def _load_area_lookup(region_slug: str) -> dict[int, float]:
    """Reutiliza área municipal de cache regional (Censo 2022 é estático)."""
    from ml.columns import Feat

    candidates = [region_population_path(region_slug), *region_population_path(region_slug).parent.glob("populacao_*.parquet")]
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        df = pd.read_parquet(path)
        if Feat.AREA_KM2 in df.columns and df[Feat.AREA_KM2].notna().all():
            return df.set_index("id_municip_ibge")[Feat.AREA_KM2].to_dict()
    return {}


def _ensure_area_column(df: pd.DataFrame, uf: str, year: int, region_slug: str) -> pd.DataFrame:
    from ml.columns import Feat

    if Feat.AREA_KM2 in df.columns and df[Feat.AREA_KM2].notna().all():
        return df

    log.info("[%s %d] enriquecendo com área IBGE (Censo 2022)…", uf, year)
    area_lookup = _load_area_lookup(region_slug)
    areas: list[float | None] = []
    for i, row in df.iterrows():
        id7 = int(row["id_municip_ibge"])
        area = area_lookup.get(id7)
        if area is None:
            area = _fetch_area_km2(id7)
            time.sleep(0.05)
        areas.append(area)

    df = df.copy()
    df[Feat.AREA_KM2] = areas
    df = df.dropna(subset=[Feat.AREA_KM2])
    df[Feat.DENSIDADE_KM2] = df["populacao"] / df[Feat.AREA_KM2]
    return df


def load_population(
    region_slug: str,
    uf: str,
    year: int | None = None,
    *,
    force: bool = False,
) -> pd.DataFrame:
    """Retorna id_municip, municipio, populacao, area_km2, densidade_km2.

    Usa um único ano de referência (REFERENCE_POP_YEAR) para todos os painéis.
    O parâmetro ``year`` só sobrescreve se informado explicitamente.
    """
    from ml.columns import Feat
    from ml.config import REFERENCE_POP_YEAR

    ref_year = REFERENCE_POP_YEAR if year is None else year
    cache = region_population_path(region_slug)
    if cache.exists() and not force:
        df = pd.read_parquet(cache)
        if Feat.DENSIDADE_KM2 not in df.columns:
            df = _ensure_area_column(df, uf, ref_year, region_slug)
            df.to_parquet(cache, index=False)
        log.info("[%s ref=%d] referência municipal em cache → %d municípios", region_slug, ref_year, len(df))
        return df

    uf_code = UF_IBGE[uf.upper()]
    resp = requests.get(IBGE_MUNICIPIOS_URL.format(uf_code=uf_code), timeout=60)
    resp.raise_for_status()
    municipios = resp.json()
    area_lookup = _load_area_lookup(region_slug)
    if area_lookup:
        log.info("[%s ref=%d] área reutilizada de cache regional (%d municípios)", region_slug, ref_year, len(area_lookup))

    rows: list[dict] = []
    for i, m in enumerate(municipios, 1):
        id7 = int(m["id"])
        id6 = id7 // 10
        pop = _fetch_population(id7, ref_year)
        area = area_lookup.get(id7)
        if area is None:
            area = _fetch_area_km2(id7)
        if pop is None or area is None:
            log.warning("[%s] dados ausentes para %s (%d)", uf, m["nome"], id6)
            continue
        rows.append(
            {
                "id_municip": id6,
                "id_municip_ibge": id7,
                "municipio": m["nome"],
                "populacao": pop,
                Feat.AREA_KM2: area,
                Feat.DENSIDADE_KM2: pop / area,
            }
        )
        if i % 50 == 0:
            log.info("[%s ref=%d] referência IBGE… %d/%d", uf, ref_year, i, len(municipios))
        time.sleep(0.05)

    df = pd.DataFrame(rows)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    write_manifest(
        cache.with_suffix(".manifest.json"),
        {
            "region": region_slug,
            "uf": uf,
            "year": ref_year,
            "municipios": len(df),
            "pop_source": IBGE_POP_URL.format(year=ref_year),
            "area_source": IBGE_AREA_URL,
            "output": str(cache.relative_to(ROOT)),
        },
    )
    log.info("[%s ref=%d] referência salva → %s (%d municípios)", region_slug, ref_year, cache, len(df))
    return df
