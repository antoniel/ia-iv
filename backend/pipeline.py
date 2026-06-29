from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from backend.checkpoint import checkpoint_lock, get_task_status, is_done, load_checkpoint, mark_done, mark_failed, mark_running, task_key
from backend.config import NORDESTE, ROOT
from backend.data import (
    export_municipios,
    export_resumo,
    extract_state_year,
    municipios_path,
    raw_csv_path,
    resumo_is_stale,
    resumo_path,
)
from backend.geo import ensure_geo, geo_path

log = logging.getLogger(__name__)


def run_state_pipeline(
    uf: str,
    years: list[int],
    *,
    force: bool = False,
    root: Path = ROOT,
) -> None:
    sigla = uf.upper()

    key_geo = task_key(sigla, "geo")
    gp = geo_path(sigla)
    if is_done(key_geo) and gp.exists() and not force:
        log.info("[%s] [1/4] geo — cache", sigla)
    else:
        log.info("[%s] [1/4] geo — baixando malha IBGE…", sigla)
        mark_running(key_geo)
        try:
            ensure_geo(sigla, root, force=force)
            mark_done(key_geo)
        except Exception as exc:
            mark_failed(key_geo, str(exc))
            raise

    for ano in years:
        out_csv = raw_csv_path(sigla, ano)

        key_ext = task_key(sigla, "extract", str(ano))
        ext_status = get_task_status(key_ext)
        if is_done(key_ext) and out_csv.exists() and not force:
            log.info("[%s %d] [2/4] extract — cache", sigla, ano)
        else:
            log.info("[%s %d] [2/4] extract — filtrando DENGBR…", sigla, ano)
            mark_running(key_ext)
            try:
                redo = force or (ext_status == "running" and out_csv.exists())
                extract_state_year(sigla, ano, force=redo)
                mark_done(key_ext)
            except Exception as exc:
                mark_failed(key_ext, str(exc))
                raise

        key_mun = task_key(sigla, "export", "municipios", str(ano))
        mp = municipios_path(sigla, ano)
        if is_done(key_mun) and mp.exists() and not force:
            log.info("[%s %d] [3/4] municípios — cache", sigla, ano)
        else:
            log.info("[%s %d] [3/4] municípios — agregando…", sigla, ano)
            mark_running(key_mun)
            try:
                export_municipios(sigla, ano, root, force=force)
                mark_done(key_mun)
            except Exception as exc:
                mark_failed(key_mun, str(exc))
                raise

    key_res = task_key(sigla, "export", "resumo")
    rp = resumo_path(sigla)
    resumo_cached = is_done(key_res) and rp.exists() and not force and not resumo_is_stale(sigla)
    if resumo_cached:
        log.info("[%s] [4/4] resumo — cache", sigla)
    else:
        log.info("[%s] [4/4] resumo — consolidando anos…", sigla)
        mark_running(key_res)
        try:
            export_resumo(sigla, force=force or resumo_is_stale(sigla))
            mark_done(key_res)
        except Exception as exc:
            mark_failed(key_res, str(exc))
            raise


def _run_state_worker(args: tuple[str, list[int], bool]) -> str:
    uf, years, force = args
    run_state_pipeline(uf, years, force=force)
    return uf


def run_nordeste(
    years: list[int],
    states: list[str] | None = None,
    *,
    force: bool = False,
    workers: int = 1,
) -> None:
    targets = [s.upper() for s in (states or NORDESTE)]
    log.info("=== Nordeste: %s | anos %s | workers=%d ===", ", ".join(targets), years, workers)

    if workers <= 1:
        for i, uf in enumerate(targets, 1):
            log.info("--- [%d/%d] %s ---", i, len(targets), uf)
            run_state_pipeline(uf, years, force=force)
    else:
        n = min(workers, len(targets))
        log.info("Processando %d UFs em paralelo…", n)
        jobs = [(uf, years, force) for uf in targets]
        with ProcessPoolExecutor(max_workers=n) as pool:
            futures = {pool.submit(_run_state_worker, job): job[0] for job in jobs}
            done = 0
            for fut in as_completed(futures):
                uf = futures[fut]
                done += 1
                fut.result()
                log.info("--- [%d/%d] %s ✓ ---", done, len(targets), uf)

    log.info("=== Concluído ===")


def state_availability(uf: str) -> dict:
    sigla = uf.upper()
    geo = get_task_status(task_key(sigla, "geo")) == "done"
    with checkpoint_lock():
        tasks = load_checkpoint().get("tasks", {})
    return {
        "uf": sigla,
        "geo": geo,
        "tasks": {
            k.split(":", 1)[1]: v.get("status", "pending")
            for k, v in tasks.items()
            if k.startswith(f"{sigla}:")
        },
    }
