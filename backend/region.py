from __future__ import annotations

import logging
from pathlib import Path

from backend.config import NORDESTE
from backend.data import load_municipios, load_resumo, municipios_path, resumo_path
from backend.geo import geo_path, load_geo

log = logging.getLogger(__name__)


def _uf_nome(uf: str) -> str:
    nomes = {
        "MA": "Maranhão",
        "PI": "Piauí",
        "CE": "Ceará",
        "RN": "Rio Grande do Norte",
        "PB": "Paraíba",
        "PE": "Pernambuco",
        "AL": "Alagoas",
        "SE": "Sergipe",
        "BA": "Bahia",
    }
    return nomes.get(uf.upper(), uf)


def is_state_ready(uf: str, ano: int) -> bool:
    sigla = uf.upper()
    return geo_path(sigla).exists() and municipios_path(sigla, ano).exists()


def ready_states(ano: int = 2024) -> list[str]:
    return [uf for uf in NORDESTE if is_state_ready(uf, ano)]


def resolve_ufs(ufs: str | None, ano: int) -> list[str]:
    if ufs:
        requested = [u.strip().upper() for u in ufs.split(",") if u.strip()]
        return [u for u in requested if is_state_ready(u, ano)]
    return ready_states(ano)


def merge_geos(ufs: list[str]) -> dict:
    features: list[dict] = []
    for uf in ufs:
        geo = load_geo(uf)
        for feat in geo.get("features", []):
            props = dict(feat.get("properties") or {})
            props["uf"] = uf.upper()
            features.append({**feat, "properties": props})
    return {"type": "FeatureCollection", "features": features}


def merge_municipios(ufs: list[str], ano: int) -> list[dict]:
    rows: list[dict] = []
    for uf in ufs:
        try:
            for row in load_municipios(uf, ano):
                rows.append({**row, "uf": uf.upper()})
        except FileNotFoundError:
            log.warning("[%s] municípios %d ausentes no merge", uf, ano)
    return rows


def region_resumo_ano(ufs: list[str], ano: int) -> list[dict]:
    out: list[dict] = []
    for uf in ufs:
        try:
            resumo = load_resumo(uf)
        except FileNotFoundError:
            continue
        row = next((r for r in resumo if r["ano"] == ano), None)
        if row:
            out.append(
                {
                    "uf": uf.upper(),
                    "nome": _uf_nome(uf),
                    "ano": ano,
                    "registros": row["registros"],
                    "municipios": row["municipios"],
                    "periodo": row["periodo"],
                }
            )
    return out
