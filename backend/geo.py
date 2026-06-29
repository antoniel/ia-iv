from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from backend.config import GEO_CACHE, IBGE_MALHAS_URL, IBGE_MUNICIPIOS_URL, UF_IBGE

log = logging.getLogger(__name__)


def geo_path(uf: str) -> Path:
    return GEO_CACHE / f"{uf.lower()}.geojson"


def legacy_geo_path(uf: str, root: Path) -> Path | None:
    """GeoJSON legado no repo (ex.: BA)."""
    if uf.upper() != "BA":
        return None
    path = root / "data/raw/geo/ba_municipios.geojson"
    return path if path.exists() else None


def download_geo(uf: str, dest: Path | None = None) -> Path:
    sigla = uf.upper()
    if sigla not in UF_IBGE:
        raise ValueError(f"UF desconhecida: {uf}")
    out = dest or geo_path(sigla)
    out.parent.mkdir(parents=True, exist_ok=True)

    url = IBGE_MALHAS_URL.format(uf_code=UF_IBGE[sigla])
    log.info("[%s] baixando malha IBGE…", sigla)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    geo = resp.json()
    out.write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")
    n = len(geo.get("features", []))
    log.info("[%s] malha salva → %s (%d municípios)", sigla, out, n)
    return out


def ensure_geo(uf: str, root: Path, force: bool = False) -> Path:
    sigla = uf.upper()
    out = geo_path(sigla)
    if out.exists() and out.stat().st_size > 0 and not force:
        log.info("[%s] malha em cache → %s", sigla, out)
        return out

    legacy = legacy_geo_path(sigla, root)
    if legacy is not None and not force:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(legacy.read_bytes())
        log.info("[%s] malha copiada do legado → %s", sigla, out)
        return out

    return download_geo(sigla, out)


def load_geo(uf: str) -> dict:
    path = geo_path(uf)
    if not path.exists():
        raise FileNotFoundError(f"Malha não encontrada para {uf}: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def codarea_maps(geo: dict) -> tuple[dict[int, str], dict[str, int]]:
    """ID_MUNICIP (6 díg) → codarea (7 díg str); codarea → id6."""
    id_to_cod: dict[int, str] = {}
    cod_to_id: dict[str, int] = {}
    for feat in geo.get("features", []):
        raw = (feat.get("properties") or {}).get("codarea")
        if raw is None:
            continue
        codarea = str(raw)
        id6 = int(codarea) // 10
        id_to_cod[id6] = codarea
        cod_to_id[codarea] = id6
    return id_to_cod, cod_to_id


def fetch_municipio_names(uf: str) -> dict[int, str]:
    sigla = uf.upper()
    url = IBGE_MUNICIPIOS_URL.format(uf_code=UF_IBGE[sigla])
    log.info("[%s] buscando nomes IBGE…", sigla)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return {int(m["id"]) // 10: m["nome"] for m in resp.json()}
