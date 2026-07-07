"""Configuração do pipeline ML (sem dependência do backend)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_ML = ROOT / "data" / "ml"
EXPERIMENTS_PATH = ROOT / "experiments" / "experiments.jsonl"

DEFAULT_CHUNKSIZE = 100_000
DEFAULT_K = 4
DEFAULT_RANDOM_STATE = 42
DEFAULT_MIN_CASOS_ANUAL = 30
REFERENCE_POP_YEAR = 2024  # população/área/densidade fixas (IBGE); não varia por ano de casos
DEFAULT_YEARS: list[int] = list(range(2016, 2026))  # 2016 a 2025
PRIMARY_METRIC = "silhouette"

UF_IBGE: dict[str, int] = {
    "RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17,
    "MA": 21, "PI": 22, "CE": 23, "RN": 24, "PB": 25, "PE": 26, "AL": 27,
    "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41,
    "SC": 42, "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53,
}

@dataclass
class RunConfig:
    region: str = "ba"
    year: int = 2024
    feature_version: str = "v0"
    k: int = DEFAULT_K
    tag: str = ""
    notes: str = ""
    random_state: int = DEFAULT_RANDOM_STATE
    download: bool = False
    force_data: bool = False

    def effective_tag(self) -> str:
        if self.tag:
            return self.tag
        return self.feature_version
