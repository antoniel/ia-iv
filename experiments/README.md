# Experimentos IA-IV

Log versionado do processo iterativo (estilo IA-III).

Cada linha em `experiments.jsonl` registra um run de clusterização: métricas internas, config, perfis médios por cluster e transições.

## Ciclo

1. Hipótese → mudar `FEATURES_Vn` em `ml/columns.py` ou passar `--version`
2. Run → `uv run ia-iv`
3. Log automático → nova linha aqui
4. Anotar → `uv run ia-iv-exp note exp_NNN "porquê da decisão"`

## Comandos

```bash
uv run ia-iv                                          # v0 baseline
uv run ia-iv --version v1 --tag v1-temporal
uv run ia-iv --data --download --force                # refresh parquet
uv run ia-iv-exp list
uv run ia-iv-exp note exp_001 "baseline trivial; evoluir para v1"
```

Métrica primária: **silhouette** (maior = melhor separação interna).
