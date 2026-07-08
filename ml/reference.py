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


def _ibge_get(url: str, params: dict, *, retries: int = 3, timeout: int = 120) -> dict | list | None:
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if not resp.ok:
                continue
            return resp.json()
        except requests.RequestException:
            if attempt == retries - 1:
                return None
            time.sleep(1.0)
    return None


def _parse_series_map(data: list | dict | None, period_key: str) -> dict[int, float]:
    """Extrai {id7: valor} de resposta agregada IBGE."""
    if not data:
        return {}
    out: dict[int, float] = {}
    try:
        series = data[0]["resultados"][0]["series"]
    except (IndexError, KeyError, TypeError):
        return {}
    for item in series:
        try:
            id7 = int(item["localidade"]["id"])
            raw = item["serie"].get(period_key)
            if raw is None or raw in {"...", "-"}:
                continue
            out[id7] = float(raw)
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _fetch_population_bulk(uf_code: int, year: int) -> dict[int, float]:
    """População de todos os municípios da UF em uma chamada."""
    data = _ibge_get(
        IBGE_POP_URL.format(year=year),
        {"localidades": f"N6[in N3[{uf_code}]]"},
    )
    return _parse_series_map(data, str(year))


def _fetch_area_bulk(uf_code: int) -> dict[int, float]:
    """Área territorial (Censo 2022) de todos os municípios da UF."""
    data = _ibge_get(
        IBGE_AREA_URL,
        {"localidades": f"N6[in N3[{uf_code}]]"},
    )
    return _parse_series_map(data, "2022")


def _fetch_population(id7: int, year: int) -> float | None:
    data = _ibge_get(IBGE_POP_URL.format(year=year), {"localidades": f"N6[{id7}]"})
    parsed = _parse_series_map(data, str(year))
    return parsed.get(id7)


def _fetch_area_km2(id7: int) -> float | None:
    data = _ibge_get(IBGE_AREA_URL, {"localidades": f"N6[{id7}]"})
    parsed = _parse_series_map(data, "2022")
    return parsed.get(id7)


def _load_area_lookup(region_slug: str) -> dict[int, float]:
    """Reutiliza área municipal de cache regional (Censo 2022 é estático)."""
    from ml.columns import Feat

    candidates = [
        region_population_path(region_slug),
        *region_population_path(region_slug).parent.glob("populacao_*.parquet"),
    ]
    seen: set[Path] = set()
    merged: dict[int, float] = {}
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        df = pd.read_parquet(path)
        if Feat.AREA_KM2 in df.columns and "id_municip_ibge" in df.columns:
            merged.update(df.set_index("id_municip_ibge")[Feat.AREA_KM2].dropna().to_dict())
    return merged


def _ensure_area_column(df: pd.DataFrame, uf: str, year: int, region_slug: str) -> pd.DataFrame:
    from ml.columns import Feat

    if Feat.AREA_KM2 in df.columns and df[Feat.AREA_KM2].notna().all():
        return df

    log.info("[%s %d] enriquecendo com área IBGE (Censo 2022)…", uf, year)
    area_lookup = _load_area_lookup(region_slug)
    areas: list[float | None] = []
    for _, row in df.iterrows():
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


def _fetch_uf_population_rows(
    uf: str,
    ref_year: int,
    area_lookup: dict[int, float],
) -> list[dict]:
    from ml.columns import Feat

    uf_code = UF_IBGE[uf.upper()]
    resp = requests.get(IBGE_MUNICIPIOS_URL.format(uf_code=uf_code), timeout=60)
    resp.raise_for_status()
    municipios = resp.json()

    log.info("[%s ref=%d] baixando população/área IBGE em lote…", uf, ref_year)
    pop_map = _fetch_population_bulk(uf_code, ref_year)
    area_map = {**area_lookup, **_fetch_area_bulk(uf_code)}

    rows: list[dict] = []
    for m in municipios:
        id7 = int(m["id"])
        id6 = id7 // 10
        pop = pop_map.get(id7)
        area = area_map.get(id7)
        if pop is None:
            pop = _fetch_population(id7, ref_year)
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
                "uf": uf.upper(),
                "populacao": pop,
                Feat.AREA_KM2: area,
                Feat.DENSIDADE_KM2: pop / area,
            }
        )
    log.info("[%s ref=%d] %d municípios com referência completa", uf, ref_year, len(rows))
    return rows


def load_population(
    region_slug: str,
    uf: str | tuple[str, ...] | list[str],
    year: int | None = None,
    *,
    force: bool = False,
) -> pd.DataFrame:
    """Retorna id_municip, municipio, populacao, area_km2, densidade_km2.

    Usa um único ano de referência (REFERENCE_POP_YEAR) para todos os painéis.
    O parâmetro ``year`` só sobrescreve se informado explicitamente.
    ``uf`` aceita uma sigla ou lista/tupla de UFs (ex.: Nordeste).
    """
    from ml.columns import Feat
    from ml.config import REFERENCE_POP_YEAR

    ufs = (uf,) if isinstance(uf, str) else tuple(u.upper() for u in uf)
    label = ufs[0] if len(ufs) == 1 else ",".join(ufs)
    ref_year = REFERENCE_POP_YEAR if year is None else year
    cache = region_population_path(region_slug)
    if cache.exists() and not force:
        df = pd.read_parquet(cache)
        if Feat.DENSIDADE_KM2 not in df.columns:
            df = _ensure_area_column(df, label, ref_year, region_slug)
            df.to_parquet(cache, index=False)
        log.info("[%s ref=%d] referência municipal em cache → %d municípios", region_slug, ref_year, len(df))
        return df

    area_lookup = _load_area_lookup(region_slug)
    for u in ufs:
        area_lookup.update(_load_area_lookup(u.lower()))
    if area_lookup:
        log.info("[%s ref=%d] área reutilizada de cache (%d municípios)", region_slug, ref_year, len(area_lookup))

    rows: list[dict] = []
    for u in ufs:
        mono = region_population_path(u.lower())
        if mono.exists() and not force and region_slug != u.lower():
            part = pd.read_parquet(mono)
            if Feat.DENSIDADE_KM2 not in part.columns:
                part = _ensure_area_column(part, u, ref_year, u.lower())
            if "uf" not in part.columns:
                part = part.copy()
                part["uf"] = u.upper()
            rows.extend(part.to_dict(orient="records"))
            log.info("[%s] reutilizando população de %s (%d municípios)", region_slug, mono, len(part))
            continue
        rows.extend(_fetch_uf_population_rows(u, ref_year, area_lookup))

    df = pd.DataFrame(rows)
    if not df.empty and "id_municip" in df.columns:
        df = df.drop_duplicates(subset=["id_municip"], keep="first")
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    write_manifest(
        cache.with_suffix(".manifest.json"),
        {
            "region": region_slug,
            "uf": label,
            "ufs": list(ufs),
            "year": ref_year,
            "municipios": len(df),
            "pop_source": IBGE_POP_URL.format(year=ref_year),
            "area_source": IBGE_AREA_URL,
            "output": str(cache.relative_to(ROOT)),
        },
    )
    log.info("[%s ref=%d] referência salva → %s (%d municípios)", region_slug, ref_year, cache, len(df))
    return df
