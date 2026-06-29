from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pandas as pd

from backend.config import DATA_PROCESSED, DATA_RAW, DEFAULT_CHUNKSIZE, EXPORT_CACHE, UF_IBGE
from backend.geo import codarea_maps, ensure_geo, fetch_municipio_names, load_geo

log = logging.getLogger(__name__)

UF_NOT_COL = "SG_UF_NOT"
MUNICIP_COL = "ID_MUNICIP"


def raw_csv_path(uf: str, ano: int) -> Path:
    yy = str(ano)[-2:]
    return DATA_PROCESSED / uf.lower() / "raw" / f"DENG{uf.upper()}{yy}.csv"


def input_csv_path(ano: int) -> Path:
    yy = str(ano)[-2:]
    return DATA_RAW / f"DENGBR{yy}.csv"


def export_dir(uf: str) -> Path:
    return EXPORT_CACHE / uf.lower()


def resumo_path(uf: str) -> Path:
    return export_dir(uf) / "resumo-anos.json"


def municipios_path(uf: str, ano: int) -> Path:
    return export_dir(uf) / f"municipios-{ano}.json"


def extract_state_year(
    uf: str,
    ano: int,
    *,
    chunksize: int = DEFAULT_CHUNKSIZE,
    force: bool = False,
    skip_existing: bool = False,
) -> Path:
    sigla = uf.upper()
    uf_code = UF_IBGE[sigla]
    inp = input_csv_path(ano)
    out = raw_csv_path(sigla, ano)

    if skip_existing and out.exists() and out.stat().st_size > 0 and not force:
        log.info("[%s %d] CSV já existe → %s", sigla, ano, out)
        return out

    if not inp.exists():
        raise FileNotFoundError(f"Arquivo nacional ausente: {inp}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    total_in = 0
    total_out = 0
    wrote_header = False
    chunk_i = 0
    t0 = time.perf_counter()
    inp_size = inp.stat().st_size
    est_rows = max(1, inp_size // 180)

    log.info("[%s %d] extraindo de %s (~%s MB)…", sigla, ano, inp.name, f"{inp_size / 1e6:.0f}")
    for chunk in pd.read_csv(inp, chunksize=chunksize, low_memory=False):
        chunk_i += 1
        total_in += len(chunk)
        if UF_NOT_COL not in chunk.columns:
            raise KeyError(f"{inp.name}: coluna {UF_NOT_COL!r} ausente")

        mask = chunk[UF_NOT_COL] == uf_code
        filtered = chunk.loc[mask]
        total_out += len(filtered)
        if filtered.empty:
            continue

        filtered.to_csv(
            out,
            mode="w" if not wrote_header else "a",
            header=not wrote_header,
            index=False,
        )
        wrote_header = True

        pct_read = min(99.9, 100 * total_in / est_rows)
        if chunk_i == 1 or chunk_i % 5 == 0:
            pct_out = 100 * total_out / total_in if total_in else 0
            log.info(
                "[%s %d] extração ~%.0f%% — chunk %d · %s lidas · %s mantidas (%.1f%% UF)",
                sigla,
                ano,
                pct_read,
                chunk_i,
                f"{total_in:,}".replace(",", "."),
                f"{total_out:,}".replace(",", "."),
                pct_out,
            )

    if not wrote_header:
        pd.DataFrame(columns=pd.read_csv(inp, nrows=0).columns).to_csv(out, index=False)

    elapsed = time.perf_counter() - t0
    pct = 100 * total_out / total_in if total_in else 0
    log.info(
        "[%s %d] extração concluída: %s/%s (%.1f%%) em %.1fs → %s",
        sigla,
        ano,
        f"{total_out:,}".replace(",", "."),
        f"{total_in:,}".replace(",", "."),
        pct,
        elapsed,
        out,
    )
    return out


def _list_raw_files(uf: str) -> list[Path]:
    d = DATA_PROCESSED / uf.lower() / "raw"
    return sorted(d.glob(f"DENG{uf.upper()}*.csv")) if d.exists() else []


def _raw_years(uf: str) -> set[int]:
    return {2000 + int(p.stem[-2:]) for p in _list_raw_files(uf)}


def resumo_is_stale(uf: str) -> bool:
    """True quando há CSVs processados que ainda não entraram no resumo-anos.json."""
    sigla = uf.upper()
    raw_years = _raw_years(sigla)
    if not raw_years:
        return False
    path = resumo_path(sigla)
    if not path.exists():
        return True
    cached_years = {row["ano"] for row in json.loads(path.read_text(encoding="utf-8"))}
    return raw_years != cached_years


def build_resumo(uf: str) -> list[dict]:
    rows: list[dict] = []
    for path in _list_raw_files(uf):
        ano = 2000 + int(path.stem[-2:])
        df = pd.read_csv(
            path,
            usecols=["ID_MUNICIP", "DT_NOTIFIC"],
            parse_dates=["DT_NOTIFIC"],
            low_memory=False,
        )
        rows.append(
            {
                "ano": ano,
                "registros": len(df),
                "municipios": int(df["ID_MUNICIP"].nunique()),
                "periodo": [
                    df["DT_NOTIFIC"].min().strftime("%Y-%m-%d"),
                    df["DT_NOTIFIC"].max().strftime("%Y-%m-%d"),
                ],
            }
        )
    return rows


def build_municipios(uf: str, ano: int, root: Path) -> list[dict]:
    csv_path = raw_csv_path(uf, ano)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV estadual ausente: {csv_path}")

    ensure_geo(uf, root)
    geo = load_geo(uf)
    id_to_cod, _ = codarea_maps(geo)
    ibge = fetch_municipio_names(uf)

    df = pd.read_csv(csv_path, usecols=["ID_MUNICIP"], low_memory=False)
    counts = df.groupby("ID_MUNICIP").size().reset_index(name="notificacoes")
    counts["codarea"] = counts["ID_MUNICIP"].map(id_to_cod)
    counts["municipio"] = counts["ID_MUNICIP"].map(lambda x: ibge.get(int(x), str(x)))
    counts = counts.dropna(subset=["codarea"])
    return counts[["codarea", "municipio", "notificacoes"]].to_dict(orient="records")


def export_resumo(uf: str, *, force: bool = False) -> Path:
    out = resumo_path(uf)
    if out.exists() and not force and not resumo_is_stale(uf):
        log.info("[%s] resumo em cache → %s", uf.upper(), out)
        return out
    if out.exists() and not force:
        log.info("[%s] resumo desatualizado — reconsolidando…", uf.upper())

    out.parent.mkdir(parents=True, exist_ok=True)
    data = build_resumo(uf)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("[%s] resumo exportado (%d anos) → %s", uf.upper(), len(data), out)
    return out


def export_municipios(uf: str, ano: int, root: Path, *, force: bool = False) -> Path:
    out = municipios_path(uf, ano)
    if out.exists() and not force:
        log.info("[%s %d] municípios em cache → %s", uf.upper(), ano, out)
        return out

    out.parent.mkdir(parents=True, exist_ok=True)
    data = build_municipios(uf, ano, root)
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    log.info("[%s %d] municípios exportados (%d) → %s", uf.upper(), ano, len(data), out)
    return out


def load_resumo(uf: str) -> list[dict]:
    sigla = uf.upper()
    if resumo_is_stale(sigla):
        export_resumo(sigla, force=True)
    path = resumo_path(sigla)
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_municipios(uf: str, ano: int) -> list[dict]:
    path = municipios_path(uf, ano)
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))
