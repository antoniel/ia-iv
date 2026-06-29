# Dengue no Nordeste — IA-IV

Visualização editorial de notificações de **dengue** (SINAN) nos **9 estados do Nordeste**, com mapas coropléticos, clusters semanais (K-means) e histórico anual.

**Stack:** Python (FastAPI + pandas + scikit-learn) · React (Vite + Leaflet + Recharts)

---

## O que este repositório contém

| Parte | Caminho | Função |
|-------|---------|--------|
| Dados brutos (não versionados) | `data/raw/DENGBR*.csv` | CSVs nacionais do SINAN, um por ano |
| Cache de processamento | `data/cache/` | Malhas IBGE, JSONs, clusters (gerado localmente) |
| CSVs por estado | `data/processed/{uf}/raw/` | Extraídos do DENGBR por UF |
| Backend | `backend/` | API FastAPI com processamento on-demand |
| Frontend | `web/` | Dashboard React |
| Scripts | `scripts/` | Download de dados, build em lote, API |

Os arquivos `DENGBR*.csv` são **grandes** (o de 2024 passa de 1,7 GB). **Não entram no Git** — baixe com o script descrito abaixo.

**Fonte oficial dos dados:** [Arboviroses — Dengue](https://dados.gov.br/dados/conjuntos-dados/arboviroses-dengue) (Portal de Dados Abertos / OpenDataSUS / SINAN).

---

## Pré-requisitos

- **Python 3.11+** (o projeto usa 3.12 em `.python-version`)
- **Node.js 18+** e **npm** (para o frontend)
- **Git**
- **~15 GB de disco livre** se for baixar todos os anos (2016–2026) e pré-processar o Nordeste
- Conexão estável com a internet (downloads e malhas IBGE)

Opcional, mas recomendado: **[uv](https://docs.astral.sh/uv/)** — gerenciador rápido de ambientes Python.

---

## 1. Clonar o repositório

```bash
git clone <URL_DO_REPOSITORIO> ia-iv
cd ia-iv
```

---

## 2. Ambiente Python

Escolha **uma** das opções abaixo. Todos os comandos Python do projeto assumem que você está na **raiz** (`ia-iv/`).

### Opção A — com `uv` (recomendado)

```bash
# Instalar uv (se ainda não tiver): https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh

# Criar venv e instalar dependências do pyproject.toml
uv sync

# Rodar qualquer script:
uv run python scripts/download_raw.py --help
```

### Opção B — com `pip` + `venv`

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows PowerShell

pip install -U pip
pip install pandas numpy scipy scikit-learn matplotlib seaborn jupyter \
  ipykernel nbconvert requests folium plotly streamlit streamlit-folium \
  fastapi "uvicorn[standard]"

# Daqui em diante, com o venv ativo:
python scripts/download_raw.py --help
```

> **Nota:** Com `uv run`, não é necessário `activate`. Com `pip`, ative o `.venv` antes de cada sessão.

---

## 3. Baixar os CSVs nacionais (obrigatório)

Os arquivos esperados ficam em `data/raw/` com estes nomes:

```
data/raw/DENGBR16.csv
data/raw/DENGBR17.csv
...
data/raw/DENGBR26.csv
```

### Script automático

```bash
# Todos os anos usados pelo projeto (2016–2026) — demora e ocupa bastante disco
uv run python scripts/download_raw.py

# Só alguns anos (útil para testar)
uv run python scripts/download_raw.py --years 2024 2025

# Ver URLs descobertas no portal
uv run python scripts/download_raw.py --list

# Baixar de novo mesmo se o CSV já existir
uv run python scripts/download_raw.py --years 2024 --force
```

O script:

1. Consulta a página do conjunto [arboviroses-dengue](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue)
2. Baixa o `.csv.zip` do bucket S3 do Ministério da Saúde
3. Extrai para `data/raw/DENGBR{aa}.csv`
4. Valida se o cabeçalho contém `SG_UF_NOT`, `ID_MUNICIP`, `DT_NOTIFIC`, `SEM_NOT`

### Download manual (alternativa)

Se o script falhar (rede, firewall, S3 indisponível):

1. Acesse [dados.gov.br → Arboviroses/Dengue](https://dados.gov.br/dados/conjuntos-dados/arboviroses-dengue) ou [dadosabertos.saude.gov.br/dataset/arboviroses-dengue](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue)
2. Baixe o recurso **CSV** do ano desejado (ex.: “Dengue - 2024”)
3. Se vier em ZIP, extraia o arquivo
4. Renomeie/coloque como `data/raw/DENGBR24.csv` (dois dígitos do ano)

---

## 4. Pré-processar o Nordeste (opcional, acelera a 1ª visita)

A API consegue processar **on-demand** (baixa malha IBGE, extrai UF, calcula clusters na primeira requisição). Para evitar espera longa na interface, rode o build em lote:

```bash
# Um ano, todas as UFs do NE (padrão: 2024)
uv run python scripts/build_nordeste.py

# Vários anos, paralelo por estado
uv run python scripts/build_nordeste.py \
  --workers 4 \
  --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026

# Só alguns estados
uv run python scripts/build_nordeste.py --states BA CE --years 2024

# Reprocessar tudo (ignora checkpoint)
uv run python scripts/build_nordeste.py --force --years 2024
```

- **Retomável:** interrompeu (`Ctrl+C`)? Rode o mesmo comando de novo — usa `data/cache/checkpoint.json`
- **Saída:** `data/cache/` (geo, export, cluster) e `data/processed/{uf}/raw/DENG{UF}{aa}.csv`

Estados do Nordeste: **MA, PI, CE, RN, PB, PE, AL, SE, BA**.

---

## 5. Subir a API (backend)

```bash
uv run python scripts/run_api.py --reload
```

- URL: **http://127.0.0.1:8000**
- Documentação interativa: **http://127.0.0.1:8000/docs**
- Endpoints principais:
  - `GET /api/meta/anos`
  - `GET /api/region/geo?ano=2024`
  - `GET /api/{uf}/cluster/weekly?ano=2024&k=4`

Deixe este terminal aberto.

---

## 6. Subir o frontend (web)

Em **outro terminal**, na pasta `web/`:

```bash
cd web
npm install
npm run dev
```

- URL: **http://127.0.0.1:5173**
- O Vite faz proxy de `/api` → `http://127.0.0.1:8000` (ver `web/vite.config.ts`)

Build de produção:

```bash
cd web
npm run build
npm run preview
```

---

## Fluxo completo do zero (copiar e colar)

```bash
# 1. Clone
git clone <URL_DO_REPOSITORIO> ia-iv && cd ia-iv

# 2. Python
uv sync

# 3. Dados (escolha: todos os anos OU só 2024 para teste rápido)
uv run python scripts/download_raw.py --years 2024
# uv run python scripts/download_raw.py   # todos 2016–2026

# 4. (Opcional) Pré-build
uv run python scripts/build_nordeste.py --workers 4 --years 2024

# 5. API — terminal 1
uv run python scripts/run_api.py --reload

# 6. Web — terminal 2
cd web && npm install && npm run dev
```

Abra **http://127.0.0.1:5173**.

---

## Estrutura de pastas

```
ia-iv/
├── backend/           # FastAPI, pipeline, cluster, geo
├── web/               # React + Vite
├── scripts/
│   ├── download_raw.py      # ← baixa DENGBR*.csv
│   ├── build_nordeste.py    # pré-processamento NE
│   └── run_api.py           # sobe uvicorn
├── data/
│   ├── raw/           # DENGBR*.csv (gitignored)
│   ├── processed/     # CSVs por UF (gitignored)
│   └── cache/         # geo, export, cluster (gitignored)
├── notebooks/         # análises exploratórias
└── pyproject.toml
```

---

## Solução de problemas

### `Nenhum DENGBR*.csv em data/raw/`

Rode `uv run python scripts/download_raw.py` ou baixe manualmente do portal (seção 3).

### API lenta na primeira requisição

Normal: está extraindo UF, baixando malha IBGE e calculando clusters. Rode `build_nordeste.py` antes ou aguarde; depois usa cache em `data/cache/`.

### `uv`: warning sobre `VIRTUAL_ENV`

Se você já tem outro venv ativo, use `deactivate` ou `uv sync` na raiz do projeto para o uv criar `.venv` local.

### Frontend não carrega dados

Confirme que a API está em `http://127.0.0.1:8000` e o proxy do Vite aponta para ela. Teste: `curl http://127.0.0.1:8000/api/meta/anos`

### Download falha com 403 / timeout

- Tente de novo mais tarde (bucket S3 do MS)
- Use `--years` com um ano só para isolar o problema
- Baixe manualmente pelo [portal](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue) e coloque em `data/raw/`

### Falta de disco

Só 2024 + cache do NE ≈ poucos GB. Todos os anos nacionais + build completo ≈ dezenas de GB. Use `--years` com recorte menor.

---

## Notebooks

```bash
uv run jupyter lab notebooks/
```

Ex.: `notebooks/analise_bases.ipynb` inventaria os `DENGBR*.csv` em `data/raw/`.

---

## Licença e dados

- Código do projeto: conforme repositório.
- Dados SINAN/Dengue: [Creative Commons Atribuição-SemDerivações 3.0](https://dadosabertos.saude.gov.br/) — Ministério da Saúde / DATASUS.

Ao publicar análises, cite a fonte: **SINAN — Arboviroses/Dengue**, Portal de Dados Abertos do SUS.
