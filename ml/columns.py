"""Colunas SINAN e conjuntos de features versionados (V0, V1, …)."""

from __future__ import annotations

from enum import StrEnum


class Col(StrEnum):
    TP_NOT = "TP_NOT"
    ID_AGRAVO = "ID_AGRAVO"
    DT_NOTIFIC = "DT_NOTIFIC"
    SEM_NOT = "SEM_NOT"
    NU_ANO = "NU_ANO"
    SG_UF_NOT = "SG_UF_NOT"
    ID_MUNICIP = "ID_MUNICIP"
    ID_REGIONA = "ID_REGIONA"
    ID_UNIDADE = "ID_UNIDADE"
    DT_SIN_PRI = "DT_SIN_PRI"
    SEM_PRI = "SEM_PRI"
    CLASSI_FIN = "CLASSI_FIN"
    CRITERIO = "CRITERIO"
    EVOLUCAO = "EVOLUCAO"


class Feat(StrEnum):
    CASOS = "casos"
    INCIDENCIA_100K = "incidencia_100k"
    MEDIA_MOVEL_3 = "media_movel_3"
    CRESCIMENTO = "crescimento"
    ACELERACAO = "aceleracao"
    SEMANA_EP = "semana_ep"
    POPULACAO = "populacao"
    AREA_KM2 = "area_km2"
    DENSIDADE_KM2 = "densidade_km2"


REQUIRED_RAW_COLS: tuple[str, ...] = (
    Col.SG_UF_NOT,
    Col.ID_MUNICIP,
    Col.DT_NOTIFIC,
    Col.SEM_NOT,
)

# +1 feature por versão (cumulativo)
FEATURES_V0: tuple[str, ...] = (Feat.CASOS,)

FEATURES_V1: tuple[str, ...] = (*FEATURES_V0, Feat.INCIDENCIA_100K)

FEATURES_V2: tuple[str, ...] = (*FEATURES_V1, Feat.MEDIA_MOVEL_3)

FEATURES_V3: tuple[str, ...] = (*FEATURES_V2, Feat.CRESCIMENTO)

FEATURES_V4: tuple[str, ...] = (*FEATURES_V3, Feat.ACELERACAO)

FEATURES_V5: tuple[str, ...] = (*FEATURES_V4, Feat.DENSIDADE_KM2)

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "v0": FEATURES_V0,
    "v1": FEATURES_V1,
    "v2": FEATURES_V2,
    "v3": FEATURES_V3,
    "v4": FEATURES_V4,
    "v5": FEATURES_V5,
}

VERSION_BLOCKS: dict[str, str] = {
    "v0": "baseline: casos",
    "v1": "+ incidência por 100 mil",
    "v2": "+ média móvel (3 semanas)",
    "v3": "+ crescimento semanal",
    "v4": "+ aceleração",
    "v5": "+ densidade populacional (hab/km²)",
}


def resolve_features(version: str) -> tuple[str, ...]:
    key = version.strip().lower()
    if key not in FEATURE_SETS:
        known = ", ".join(sorted(FEATURE_SETS))
        raise ValueError(f"Versão de features desconhecida: {version!r}. Opções: {known}")
    return FEATURE_SETS[key]
