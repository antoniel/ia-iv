#!/usr/bin/env python3
"""Pré-processa Nordeste: malha IBGE, extração DENGBR→estadual, export JSON.

Retomável via data/cache/checkpoint.json — tarefas concluídas são puladas.

>> uv run python scripts/build_nordeste.py
>> uv run python scripts/build_nordeste.py --states CE PE --years 2024
>> uv run python scripts/build_nordeste.py --workers 4
>> uv run python scripts/build_nordeste.py --workers 4 --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import NORDESTE
from backend.pipeline import run_nordeste

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build cache Nordeste (geo + extract + export).")
    p.add_argument(
        "--states",
        nargs="*",
        default=None,
        help=f"UFs (padrão: todas do NE: {', '.join(NORDESTE)})",
    )
    p.add_argument(
        "--years",
        nargs="*",
        type=int,
        default=[2024],
        help="Anos a processar (padrão: 2024)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 4),
        help="UFs em paralelo (padrão: min(4, CPUs))",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Reprocessar mesmo com checkpoint/arquivos existentes",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Log DEBUG")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    states = [s.upper() for s in args.states] if args.states else None
    if states:
        bad = [s for s in states if s not in NORDESTE]
        if bad:
            log.error("UFs fora do Nordeste: %s", ", ".join(bad))
            return 1

    t0 = time.perf_counter()
    try:
        run_nordeste(args.years, states=states, force=args.force, workers=max(1, args.workers))
    except KeyboardInterrupt:
        log.warning("Interrompido — rode de novo para retomar do checkpoint.")
        return 130
    except Exception:
        log.exception("Falha no pipeline")
        return 1

    log.info("Tempo total: %.1fs", time.perf_counter() - t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
