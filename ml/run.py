#!/usr/bin/env python3
"""Pipeline iterativo IA-IV: dados → features (memória) → cluster → experiments.jsonl.

Unidade de análise: **município × semana epidemiológica** (ex.: Bahia inteira).

Uso:
  uv run ia-iv                              # v0 baseline, BA 2024
  uv run ia-iv --version v5 --tag v5-densidade
  uv run ia-iv --data                       # parquet agregado BA (2016 a 2025)
  uv run ia-iv --data --force               # reconstruir dengue.parquet
  uv run ia-iv-exp list
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.cluster import run_kmeans
from ml.config import DEFAULT_K, DEFAULT_YEARS, RunConfig
from ml.dataset import build_features_panel
from ml.experiments import append_experiment
from ml.paths import region_parquet_path
from ml.preprocess import build_region_parquet
from ml.regions import resolve_region
from ml.validate import summarize_result

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pipeline ML iterativo IA-IV (município×semana)")
    p.add_argument("--region", default="ba", help="Região/UF agregada (padrão: ba)")
    p.add_argument("--year", type=int, default=2024, help="Ano analisado no experimento")
    p.add_argument("--version", default="v0", help="Conjunto de features: v0…v5 ou core")
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--tag", default="", help="Tag no log (padrão: --version)")
    p.add_argument("--notes", default="", help="Anotação inicial do experimento")
    p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--data", action="store_true", help="Só preparar dengue.parquet agregado")
    p.add_argument("--download", action="store_true", help="Baixar DENGBR antes de extrair")
    p.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=None,
        help=f"Anos no parquet agregado (padrão: {DEFAULT_YEARS[0]} a {DEFAULT_YEARS[-1]})",
    )
    p.add_argument("--force", action="store_true", help="Reprocessar parquet/população")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def run_download(years: list[int], *, force: bool) -> None:
    from scripts.download_raw import main as download_main

    argv = ["--years", *[str(y) for y in years]]
    if force:
        argv.append("--force")
    if download_main(argv) != 0:
        raise SystemExit(1)


def ensure_data(config: RunConfig, years: list[int]) -> None:
    region = resolve_region(config.region)
    if config.download:
        run_download(years, force=config.force_data)
    build_region_parquet(region, years, force=config.force_data)


def run_experiment(config: RunConfig, years: list[int]) -> dict:
    region = resolve_region(config.region)
    ensure_data(config, years)

    panel = build_features_panel(region, config.year, config.feature_version)
    data_path = region_parquet_path(region.slug)

    result = run_kmeans(
        panel,
        config.feature_version,
        k=config.k,
        random_state=config.random_state,
    )
    summary = summarize_result(panel, result)

    metrics = {
        **result.metrics,
        "n_samples": result.n_samples,
        "n_features": result.n_features,
        "n_municipios": summary["n_municipios"],
        "n_semanas": summary["n_semanas"],
    }

    record = append_experiment(
        config=config,
        metrics=metrics,
        cluster_means=summary["cluster_means"],
        cluster_sizes=summary["cluster_sizes"],
        data_path=str(data_path.relative_to(ROOT)),
        extra={
            "transitions": summary["transitions"],
            "n_municipios": summary["n_municipios"],
        },
    )

    sil = metrics.get("silhouette")
    sil_txt = f"{sil:.4f}" if sil is not None else "n/a"
    log.info(
        "%s | tag=%s | silhouette=%s | delta=%s | k=%d | linhas=%d | municípios=%d",
        record["id"],
        record["tag"],
        sil_txt,
        record.get("delta_vs_best"),
        config.k,
        result.n_samples,
        summary["n_municipios"],
    )
    log.info("Log → experiments/experiments.jsonl")
    log.info("Anotar: uv run ia-iv-exp note %s \"...\"", record["id"])
    return record


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    years = args.years or DEFAULT_YEARS
    config = RunConfig(
        region=args.region,
        year=args.year,
        feature_version=args.version,
        k=args.k,
        tag=args.tag,
        notes=args.notes,
        random_state=args.random_state,
        download=args.download,
        force_data=args.force,
    )

    if args.data:
        ensure_data(config, years)
        log.info("Parquet agregado pronto.")
        return 0

    run_experiment(config, years)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
