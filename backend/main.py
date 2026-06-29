from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.cluster import get_weekly_clusters
from backend.config import DEFAULT_K, DEFAULT_MIN_CASOS, NORDESTE, ROOT, UF_IBGE
from backend.data import load_municipios, load_resumo, municipios_path, resumo_path
from backend.ensure import available_input_years, ensure_state_year, ensure_ufs_year
from backend.geo import ensure_geo, geo_path, load_geo
from backend.pipeline import state_availability
from backend.region import (
    is_state_ready,
    merge_geos,
    merge_municipios,
    ready_states,
    region_resumo_ano,
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    yield


app = FastAPI(title="IA-IV Dengue API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/meta/anos")
def list_anos() -> dict:
    anos = set(available_input_years())
    for uf in NORDESTE:
        try:
            for row in load_resumo(uf):
                anos.add(int(row["ano"]))
        except FileNotFoundError:
            continue
    if not anos:
        raise HTTPException(
            503,
            "Nenhum DENGBR*.csv em data/raw/. Baixe os arquivos nacionais do SINAN.",
        )
    return {"anos": sorted(anos, reverse=True)}


@app.get("/api/meta/states")
def list_states(ano: int = Query(..., ge=2000, le=2100)) -> dict:
    states = []
    for uf in NORDESTE:
        avail = state_availability(uf)
        states.append(
            {
                "uf": uf,
                "nome": _uf_nome(uf),
                "ibge": UF_IBGE[uf],
                "geo_ready": geo_path(uf).exists(),
                "resumo_ready": resumo_path(uf).exists(),
                "municipios_ready": municipios_path(uf, ano).exists(),
                "ready": is_state_ready(uf, ano),
                "tasks": avail.get("tasks", {}),
            }
        )
    ready = ready_states(ano)
    return {"region": "nordeste", "states": states, "ready": ready, "ano": ano}


def _target_ufs(ufs: str | None) -> list[str]:
    if ufs:
        return [u.strip().upper() for u in ufs.split(",") if u.strip()]
    return list(NORDESTE)


@app.get("/api/region/geo")
def api_region_geo(
    ano: int = Query(..., ge=2000, le=2100),
    ufs: str | None = Query(None),
):
    targets = _target_ufs(ufs)
    log.info("GET /region/geo ano=%d ufs=%s", ano, targets)
    computed = ensure_ufs_year(targets, ano)
    selected = [u for u in targets if is_state_ready(u, ano)]
    if not selected:
        raise HTTPException(404, f"Não foi possível preparar dados para {ano}.")
    return {"ufs": selected, "geo": merge_geos(selected), "computed": computed}


@app.get("/api/region/municipios")
def api_region_municipios(
    ano: int = Query(..., ge=2000, le=2100),
    ufs: str | None = Query(None),
):
    targets = _target_ufs(ufs)
    computed = ensure_ufs_year(targets, ano)
    selected = [u for u in targets if is_state_ready(u, ano)]
    if not selected:
        raise HTTPException(404, f"Não foi possível preparar dados para {ano}.")
    return {
        "ufs": selected,
        "municipios": merge_municipios(selected, ano),
        "computed": computed,
    }


@app.get("/api/region/resumo-ano")
def api_region_resumo_ano(
    ano: int = Query(..., ge=2000, le=2100),
    ufs: str | None = Query(None),
):
    targets = _target_ufs(ufs)
    computed = ensure_ufs_year(targets, ano)
    selected = [u for u in targets if is_state_ready(u, ano)]
    if not selected:
        raise HTTPException(404, f"Não foi possível preparar dados para {ano}.")
    return {
        "ano": ano,
        "states": region_resumo_ano(selected, ano),
        "computed": computed,
    }


@app.get("/api/{uf}/geo")
def api_geo(uf: str):
    _validate_uf(uf)
    ensure_geo(uf, ROOT)
    return load_geo(uf)


@app.get("/api/{uf}/resumo")
def api_resumo(uf: str, ano: int = Query(..., ge=2000, le=2100)):
    _validate_uf(uf)
    computed = ensure_state_year(uf, ano)
    return load_resumo(uf)


@app.get("/api/{uf}/municipios")
def api_municipios(uf: str, ano: int = Query(..., ge=2000, le=2100)):
    _validate_uf(uf)
    computed = ensure_state_year(uf, ano)
    return load_municipios(uf, ano)


@app.get("/api/{uf}/cluster/weekly")
def api_cluster_weekly(
    uf: str,
    ano: int = Query(..., ge=2000, le=2100),
    k: int = Query(DEFAULT_K, ge=2, le=8),
    min_casos: int = Query(DEFAULT_MIN_CASOS, ge=1, le=500),
    force: bool = Query(False),
):
    _validate_uf(uf)
    data_computed = ensure_state_year(uf, ano, force=force)
    try:
        payload, cached = get_weekly_clusters(uf, ano, k=k, min_casos=min_casos, force=force)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    return {
        **payload,
        "cached": cached and not data_computed,
        "computed": data_computed,
    }


def _validate_uf(uf: str) -> None:
    sigla = uf.upper()
    if sigla not in UF_IBGE:
        raise HTTPException(400, f"UF inválida: {uf}")
    if sigla not in NORDESTE:
        raise HTTPException(400, f"Por enquanto só Nordeste: {', '.join(NORDESTE)}")


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
