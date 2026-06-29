from __future__ import annotations

import logging

from backend.config import DATA_RAW, NORDESTE
from backend.pipeline import run_state_pipeline
from backend.region import is_state_ready

log = logging.getLogger(__name__)


def available_input_years() -> list[int]:
    anos: set[int] = set()
    for path in DATA_RAW.glob("DENGBR*.csv"):
        anos.add(2000 + int(path.stem[-2:]))
    return sorted(anos, reverse=True)


def ensure_state_year(uf: str, ano: int, *, force: bool = False) -> bool:
    """Garante geo + CSV + JSON para UF/ano. Retorna True se computou agora."""
    sigla = uf.upper()
    if is_state_ready(sigla, ano) and not force:
        log.info("[%s %d] ✓ cache pronto", sigla, ano)
        return False
    log.info("[%s %d] ▶ preparando on-demand (geo → extract → export)…", sigla, ano)
    run_state_pipeline(sigla, [ano], force=force)
    log.info("[%s %d] ✓ pronto", sigla, ano)
    return True


def ensure_ufs_year(ufs: list[str], ano: int, *, force: bool = False) -> list[str]:
    total = len(ufs)
    computed: list[str] = []
    log.info("ensure %d UF(s) para %d — início", total, ano)
    for i, uf in enumerate(ufs, 1):
        log.info("—— [%d/%d] %s ————", i, total, uf.upper())
        if ensure_state_year(uf, ano, force=force):
            computed.append(uf.upper())
    log.info(
        "ensure concluído: %d/%d computados agora · %d cache",
        len(computed),
        total,
        total - len(computed),
    )
    return computed


def ensure_nordeste_year(ano: int, *, force: bool = False) -> list[str]:
    return ensure_ufs_year(list(NORDESTE), ano, force=force)
