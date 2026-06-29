from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data/raw"
DATA_PROCESSED = ROOT / "data/processed"
CACHE_ROOT = ROOT / "data/cache"
CHECKPOINT_PATH = CACHE_ROOT / "checkpoint.json"
GEO_CACHE = CACHE_ROOT / "geo"
EXPORT_CACHE = CACHE_ROOT / "export"
CLUSTER_CACHE = CACHE_ROOT / "cluster"

UF_IBGE: dict[str, int] = {
    "RO": 11,
    "AC": 12,
    "AM": 13,
    "RR": 14,
    "PA": 15,
    "AP": 16,
    "TO": 17,
    "MA": 21,
    "PI": 22,
    "CE": 23,
    "RN": 24,
    "PB": 25,
    "PE": 26,
    "AL": 27,
    "SE": 28,
    "BA": 29,
    "MG": 31,
    "ES": 32,
    "RJ": 33,
    "SP": 35,
    "PR": 41,
    "SC": 42,
    "RS": 43,
    "MS": 50,
    "MT": 51,
    "GO": 52,
    "DF": 53,
}

NORDESTE: tuple[str, ...] = ("MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA")

IBGE_MALHAS_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf_code}"
    "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio"
)
IBGE_MUNICIPIOS_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf_code}/municipios"
)

DEFAULT_K = 4
DEFAULT_MIN_CASOS = 30
DEFAULT_CHUNKSIZE = 100_000
