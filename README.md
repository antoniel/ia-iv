# IA-IV — Dengue (SINAN)

Trabalho de Aprendizado de Máquina com notificações de dengue do SINAN.

## Pergunta (rascunho)

> A partir das notificações de dengue na Bahia, identificamos **perfis epidêmicos municipais** ou **surtos atípicos** (município × semana)

## Fonte de dados

- Portal: [Arboviroses — Dengue](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue)
- API (amostras): `https://apidadosabertos.saude.gov.br/arboviroses/dengue`
- Dicionário SINAN: [PDF dengue](https://portalsinan.saude.gov.br/images/documentos/Agravos/Dengue/DIC_DADOS_ONLINE.pdf)

## Estrutura

```text
ia-iv/
├── README.md
├── requirements.txt
├── logs.md              # log do que foi feito (base do relatório)
├── data/
│   ├── raw/               # CSV/DBC baixados
│   ├── interim/           # limpo, filtrado
│   └── processed/         # agregado município×semana, features
├── notebooks/
│   └── hello.ipynb        # smoke test do ambiente
└── slides/                # apresentação (10 min)
```

## Setup

```bash
cd ia-iv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook notebooks/hello.ipynb
```

## Pipeline (previsto)

1. **Coleta** → `data/raw/`
2. **Limpeza** → `data/interim/` (BA, datas, `"nan"` → NA)
3. **Agregação** → `data/processed/` (município × semana, taxa/100k hab.)
4. **Modelo** → notebook NS (cluster ou anomalia)
5. **Figuras** → `slides/` + entradas no `DIARIO.md`

## Diário de trabalho

Registre cada sessão em [`logs.md`](logs.md), isso vai servir de rascunho direto para o relatório final.
