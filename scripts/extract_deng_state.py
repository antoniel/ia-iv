#!/usr/bin/env python3
"""Extrai notificações de dengue filtradas pelo local de notificação (UF/município).

Lê DENGBR*.csv em data/raw/ e grava DENGB{UF}*.csv em data/processed/{uf}/raw/.

Filtro principal: SG_UF_NOT == código IBGE da UF (ex.: BA → 29).
Opcionalmente restringe ID_MUNICIP a códigos de um GeoJSON de municípios.

>> uv run python scripts/extract_deng_state.py --state BA
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

# --- configuração padrão (sobrescrevível via CLI) ---------------------------

DEFAULT_STATE = "BA"
DEFAULT_INPUT_DIR = Path("data/raw")
DEFAULT_OUTPUT_ROOT = Path("data/processed")
DEFAULT_CHUNKSIZE = 100_000

UF_NOT_COL = "SG_UF_NOT"
MUNICIP_COL = "ID_MUNICIP"

# Sigla IBGE → código numérico (SG_UF_NOT nos CSVs SINAN)
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

# -----------------------------------------------------------------------------


def project_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "data" / "raw").exists():
        return cwd
    if (cwd.parent / "data" / "raw").exists():
        return cwd.parent
    raise FileNotFoundError("Não encontrei data/raw/ a partir do diretório atual.")


def resolve_uf_code(state: str) -> tuple[str, int]:
    sigla = state.strip().upper()
    if sigla in UF_IBGE:
        return sigla, UF_IBGE[sigla]
    if sigla.isdigit():
        code = int(sigla)
        for s, c in UF_IBGE.items():
            if c == code:
                return s, code
        return f"UF{code}", code
    raise ValueError(
        f"UF desconhecida: {state!r}. Use sigla (ex.: BA) ou código IBGE (ex.: 29)."
    )


def default_geojson(root: Path, state_sigla: str) -> Path | None:
    """GeoJSON automático só para BA (se existir). Outros estados: filtro só por UF."""
    if state_sigla != "BA":
        return None
    path = root / "data/raw/geo/ba_municipios.geojson"
    return path if path.exists() else None


def load_municipio_codes(geojson_path: Path) -> set[int]:
    """Códigos de município como aparecem em ID_MUNICIP (6 dígitos, sem DV)."""
    with geojson_path.open(encoding="utf-8") as f:
        geo = json.load(f)

    codes: set[int] = set()
    for feature in geo.get("features", []):
        props = feature.get("properties") or {}
        raw = props.get("codarea") or props.get("CD_MUN") or props.get("code")
        if raw is None:
            continue
        codarea = int(raw)
        codes.add(codarea // 10 if codarea >= 1_000_000 else codarea)
    if not codes:
        raise ValueError(f"Nenhum código de município em {geojson_path}")
    return codes


def output_name(input_name: str, state_sigla: str) -> str:
    """DENGBR24.csv → DENGBA24.csv"""
    if input_name.upper().startswith("DENGBR"):
        return f"DENG{state_sigla}{input_name[6:]}"
    stem = Path(input_name).stem
    suffix = Path(input_name).suffix
    return f"{stem}_{state_sigla.lower()}{suffix}"


def iter_input_files(input_dir: Path, years: list[str] | None) -> list[Path]:
    files = sorted(input_dir.glob("DENGBR*.csv"))
    if years:
        year_set = {y.zfill(2) for y in years}
        files = [p for p in files if p.stem[-2:] in year_set]
    return files


def extract_file(
    input_path: Path,
    output_path: Path,
    uf_code: int,
    municipio_codes: set[int] | None,
    chunksize: int,
) -> tuple[int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    total_in = 0
    total_out = 0
    wrote_header = False

    for chunk in pd.read_csv(input_path, chunksize=chunksize, low_memory=False):
        total_in += len(chunk)

        if UF_NOT_COL not in chunk.columns:
            raise KeyError(f"{input_path.name}: coluna {UF_NOT_COL!r} ausente")

        mask = chunk[UF_NOT_COL] == uf_code
        if municipio_codes is not None:
            if MUNICIP_COL not in chunk.columns:
                raise KeyError(f"{input_path.name}: coluna {MUNICIP_COL!r} ausente")
            mask &= chunk[MUNICIP_COL].isin(municipio_codes)

        filtered = chunk.loc[mask]
        total_out += len(filtered)
        if filtered.empty:
            continue

        filtered.to_csv(
            output_path,
            mode="w" if not wrote_header else "a",
            header=not wrote_header,
            index=False,
        )
        wrote_header = True

    if not wrote_header:
        pd.DataFrame(columns=pd.read_csv(input_path, nrows=0).columns).to_csv(
            output_path, index=False
        )

    return total_in, total_out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrai DENGBR*.csv filtrando pelo local de notificação (SG_UF_NOT)."
    )
    parser.add_argument(
        "--state",
        default=DEFAULT_STATE,
        help=f"Sigla ou código IBGE da UF (padrão: {DEFAULT_STATE})",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help=f"Diretório de entrada (padrão: <projeto>/{DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Diretório de saída (padrão: data/processed/{uf}/raw)",
    )
    parser.add_argument(
        "--geojson",
        type=Path,
        default=None,
        help="GeoJSON de municípios para filtrar ID_MUNICIP (BA usa ba_municipios.geojson por padrão)",
    )
    parser.add_argument(
        "--no-geojson",
        action="store_true",
        help="Filtrar apenas por SG_UF_NOT, sem restringir ID_MUNICIP",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=DEFAULT_CHUNKSIZE,
        help=f"Linhas por chunk na leitura (padrão: {DEFAULT_CHUNKSIZE})",
    )
    parser.add_argument(
        "--years",
        nargs="*",
        help="Anos a processar, ex.: 24 25 26 (padrão: todos os DENGBR*.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só lista arquivos e destinos, sem gravar",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = project_root()

    state_sigla, uf_code = resolve_uf_code(args.state)
    input_dir = (args.input_dir or root / DEFAULT_INPUT_DIR).resolve()
    output_dir = (
        args.output_dir or root / DEFAULT_OUTPUT_ROOT / state_sigla.lower() / "raw"
    ).resolve()

    geojson_path: Path | None = None
    if not args.no_geojson:
        geojson_path = args.geojson or default_geojson(root, state_sigla)
        if geojson_path is not None and not geojson_path.is_absolute():
            geojson_path = root / geojson_path

    municipio_codes: set[int] | None = None
    if geojson_path is not None:
        if not geojson_path.exists():
            print(
                f"Aviso: GeoJSON não encontrado ({geojson_path}); filtro só por UF.",
                file=sys.stderr,
            )
        else:
            municipio_codes = load_municipio_codes(geojson_path)
            print(f"Municípios no GeoJSON: {len(municipio_codes)}")

    files = iter_input_files(input_dir, args.years)
    if not files:
        print(f"Nenhum DENGBR*.csv em {input_dir}", file=sys.stderr)
        return 1

    print(f"UF: {state_sigla} (SG_UF_NOT={uf_code})")
    print(f"Entrada:  {input_dir}")
    print(f"Saída:    {output_dir}")
    print(f"Arquivos: {len(files)}")
    print("-" * 60)

    if args.dry_run:
        for path in files:
            print(f"  {path.name} → {output_name(path.name, state_sigla)}")
        return 0

    grand_in = 0
    grand_out = 0
    t0 = time.perf_counter()

    for path in files:
        out_path = output_dir / output_name(path.name, state_sigla)
        t1 = time.perf_counter()
        n_in, n_out = extract_file(
            path, out_path, uf_code, municipio_codes, args.chunksize
        )
        elapsed = time.perf_counter() - t1
        pct = 100 * n_out / n_in if n_in else 0
        print(
            f"{path.name}: {n_out:,}/{n_in:,} ({pct:.1f}%) → {out_path.name} [{elapsed:.1f}s]".replace(
                ",", "."
            )
        )
        grand_in += n_in
        grand_out += n_out

    total_elapsed = time.perf_counter() - t0
    pct_total = 100 * grand_out / grand_in if grand_in else 0
    print("-" * 60)
    print(
        f"Total: {grand_out:,}/{grand_in:,} ({pct_total:.1f}%) em {total_elapsed:.1f}s".replace(
            ",", "."
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
