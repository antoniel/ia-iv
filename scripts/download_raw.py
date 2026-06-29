#!/usr/bin/env python3
"""Baixa os CSV nacionais DENGBR*.csv do Portal de Dados Abertos (SINAN/Dengue).

Fonte oficial:
  https://dados.gov.br/dados/conjuntos-dados/arboviroses-dengue
  https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue

Os arquivos são publicados como ZIP no bucket S3 do MS. Este script baixa o ZIP,
extrai o CSV para data/raw/DENGBR{aa}.csv e valida o cabeçalho mínimo.

Uso:
  uv run python scripts/download_raw.py
  uv run python scripts/download_raw.py --years 2024 2025
  uv run python scripts/download_raw.py --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026
  uv run python scripts/download_raw.py --force
  uv run python scripts/download_raw.py --list
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import DATA_RAW

log = logging.getLogger(__name__)

DATASET_PAGE = "https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue"
S3_ZIP_TEMPLATE = (
    "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR{yy}.csv.zip"
)
USER_AGENT = "ia-iv-dengue/0.1 (+https://github.com; dados abertos MS/SINAN)"
REQUIRED_COLS = ("SG_UF_NOT", "ID_MUNICIP", "DT_NOTIFIC", "SEM_NOT")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Baixa DENGBR*.csv para data/raw/")
    p.add_argument(
        "--years",
        nargs="*",
        type=int,
        default=list(range(2016, 2027)),
        help="Anos a baixar (padrão: 2016–2026)",
    )
    p.add_argument("--force", action="store_true", help="Substituir CSVs já existentes")
    p.add_argument("--list", action="store_true", help="Listar URLs disponíveis e sair")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def discover_zip_urls(session: requests.Session) -> dict[int, str]:
    """Lê a página do conjunto de dados e mapeia ano → URL do .csv.zip."""
    log.info("Consultando recursos em %s …", DATASET_PAGE)
    resp = session.get(DATASET_PAGE, timeout=120)
    resp.raise_for_status()
    found: dict[int, str] = {}
    for url, yy in re.findall(
        r"(https://s3[^\s\"<>]+/DENGBR(\d{2})\.csv\.zip)",
        resp.text,
    ):
        found[2000 + int(yy)] = url
    if not found:
        log.warning("Nenhuma URL S3 encontrada na página — usando template padrão.")
    return found


def zip_url_for_year(year: int, discovered: dict[int, str]) -> str:
    if year in discovered:
        return discovered[year]
    yy = str(year)[-2:]
    return S3_ZIP_TEMPLATE.format(yy=yy)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"


def download_zip(session: requests.Session, url: str, dest_zip: Path) -> None:
    log.info("Baixando %s …", url)
    with session.get(url, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        chunks: list[bytes] = []
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            chunks.append(chunk)
            done += len(chunk)
            if total:
                pct = 100 * done / total
                log.info("  … %s / %s (%.0f%%)", human_size(done), human_size(total), pct)
        dest_zip.write_bytes(b"".join(chunks))
    log.info("ZIP salvo (%s) → %s", human_size(dest_zip.stat().st_size), dest_zip)


def extract_csv(zip_path: Path, csv_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise RuntimeError(f"ZIP sem CSV: {zip_path}")
        if len(members) > 1:
            members.sort(key=len)
        name = members[0]
        log.info("Extraindo %s …", name)
        with zf.open(name) as src, csv_path.open("wb") as dst:
            while True:
                block = src.read(1024 * 1024)
                if not block:
                    break
                dst.write(block)


def validate_csv(csv_path: Path) -> None:
    with csv_path.open("r", encoding="utf-8", errors="replace") as f:
        header = f.readline()
    cols = header.strip().split(",")
    missing = [c for c in REQUIRED_COLS if c not in cols]
    if missing:
        raise RuntimeError(
            f"{csv_path.name}: colunas ausentes {missing}. "
            f"Verifique se o arquivo é o CSV SINAN de dengue."
        )


def fetch_year(
    session: requests.Session,
    year: int,
    discovered: dict[int, str],
    *,
    force: bool,
) -> Path:
    yy = str(year)[-2:]
    csv_path = DATA_RAW / f"DENGBR{yy}.csv"
    if csv_path.exists() and not force:
        log.info("[%d] %s já existe — pulando (use --force)", year, csv_path.name)
        return csv_path

    DATA_RAW.mkdir(parents=True, exist_ok=True)
    url = zip_url_for_year(year, discovered)
    zip_path = DATA_RAW / f"DENGBR{yy}.csv.zip"

    try:
        download_zip(session, url, zip_path)
        extract_csv(zip_path, csv_path)
        validate_csv(csv_path)
    finally:
        if zip_path.exists():
            zip_path.unlink()

    log.info("[%d] ✓ %s (%s)", year, csv_path.name, human_size(csv_path.stat().st_size))
    return csv_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    discovered = discover_zip_urls(session)
    if args.list:
        for year in sorted(discovered):
            print(f"{year}\t{discovered[year]}")
        return 0

    years = sorted(set(args.years))
    log.info("Destino: %s | anos: %s", DATA_RAW, years)

    errors: list[str] = []
    for year in years:
        try:
            fetch_year(session, year, discovered, force=args.force)
        except Exception as exc:
            log.error("[%d] falhou: %s", year, exc)
            errors.append(f"{year}: {exc}")

    if errors:
        log.error("Concluído com erros (%d/%d):", len(errors), len(years))
        for msg in errors:
            log.error("  • %s", msg)
        return 1

    log.info("Todos os %d arquivo(s) prontos em %s", len(years), DATA_RAW)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
