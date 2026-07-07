# Dados ML

Artefatos em disco por região (`data/ml/{slug}/`):

| Arquivo | Conteúdo |
| --- | --- |
| `dengue.parquet` | notificações agregadas (coluna `year`) |
| `dengue.manifest.json` | metadados e contagem por ano |
| `populacao.parquet` | população, área e densidade IBGE (referência única) |

Features v0…v5 e painéis de cluster são construídos **em memória** (notebooks / `uv run ia-iv`).

Gerar o parquet agregado:

```bash
uv run ia-iv --data --region ba
uv run ia-iv --region ba --year 2024 --version v5
```

Unidade de clusterização: **município × semana epidemiológica**.
