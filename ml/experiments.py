"""Log de experimentos em JSONL (estilo IA-III)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from ml.config import EXPERIMENTS_PATH, PRIMARY_METRIC, ROOT, RunConfig


def _ensure_log() -> None:
    EXPERIMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not EXPERIMENTS_PATH.exists():
        EXPERIMENTS_PATH.write_text("", encoding="utf-8")


def load_experiments() -> list[dict[str, Any]]:
    _ensure_log()
    rows: list[dict[str, Any]] = []
    for line in EXPERIMENTS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _next_id(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "exp_001"
    last = max(int(r["id"].split("_")[1]) for r in rows if r.get("id", "").startswith("exp_"))
    return f"exp_{last + 1:03d}"


def _best_metric(rows: list[dict[str, Any]], metric: str) -> float | None:
    values = [
        r["metrics"][metric]
        for r in rows
        if r.get("metrics", {}).get(metric) is not None
    ]
    return max(values) if values else None


def append_experiment(
    *,
    config: RunConfig,
    metrics: dict[str, float | None],
    cluster_means: dict[str, Any],
    cluster_sizes: dict[int, int],
    data_path: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = load_experiments()
    exp_id = _next_id(rows)
    best = _best_metric(rows, PRIMARY_METRIC)
    primary = metrics.get(PRIMARY_METRIC)
    delta = None
    if primary is not None and best is not None:
        delta = round(primary - best, 4)

    from ml.columns import resolve_features

    record: dict[str, Any] = {
        "id": exp_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tag": config.effective_tag(),
        "notes": config.notes,
        "metrics": metrics,
        "delta_vs_best": delta,
        "is_best": primary is not None and (best is None or primary >= best),
        "config": {
            "region": config.region,
            "year": config.year,
            "feature_version": config.feature_version,
            "features": list(resolve_features(config.feature_version)),
            "k": config.k,
            "random_state": config.random_state,
        },
        "cluster_means": cluster_means,
        "cluster_sizes": {str(k): v for k, v in cluster_sizes.items()},
        "data_path": data_path,
        "n_samples": metrics.get("n_samples"),
        "n_features": metrics.get("n_features"),
    }
    if extra:
        record.update(extra)

    with EXPERIMENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def update_notes(exp_id: str, notes: str) -> dict[str, Any]:
    rows = load_experiments()
    updated: dict[str, Any] | None = None
    out_lines: list[str] = []
    for row in rows:
        if row.get("id") == exp_id:
            row["notes"] = notes
            updated = row
        out_lines.append(json.dumps(row, ensure_ascii=False))
    if updated is None:
        raise KeyError(f"Experimento não encontrado: {exp_id}")
    EXPERIMENTS_PATH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return updated


def list_experiments() -> None:
    rows = load_experiments()
    if not rows:
        print("(vazio)")
        return
    print(f"{'id':<8} {'tag':<12} {'silhouette':>10} {'delta':>8} {'k':>3}  notes")
    print("-" * 72)
    for row in rows:
        m = row.get("metrics", {})
        sil = m.get("silhouette")
        sil_s = f"{sil:.4f}" if sil is not None else "   n/a"
        delta = row.get("delta_vs_best")
        delta_s = f"{delta:+.4f}" if delta is not None else "     n/a"
        cfg = row.get("config", {})
        notes = (row.get("notes") or "")[:40]
        print(
            f"{row['id']:<8} {row.get('tag',''):<12} {sil_s:>10} {delta_s:>8} "
            f"{cfg.get('k','?'):>3}  {notes}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Histórico de experimentos IA-IV")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Listar experimentos")

    note = sub.add_parser("note", help="Anotar experimento")
    note.add_argument("exp_id", help="ex.: exp_001")
    note.add_argument("notes", nargs="+", help="Texto da anotação")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.cmd == "list":
        list_experiments()
        return 0
    if args.cmd == "note":
        updated = update_notes(args.exp_id, " ".join(args.notes))
        print(f"✓ {updated['id']}: {updated['notes']}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
