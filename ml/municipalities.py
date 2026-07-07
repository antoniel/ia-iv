"""Recorte municipal para iteração rápida no pipeline de ML."""

from __future__ import annotations

from dataclasses import dataclass

from ml.config import UF_IBGE


@dataclass(frozen=True, slots=True)
class MunicipioSpec:
    slug: str
    name: str
    id_municip: int
    uf: str

    @property
    def uf_code(self) -> int:
        return UF_IBGE[self.uf.upper()]


SALVADOR = MunicipioSpec(
    slug="salvador",
    name="Salvador",
    id_municip=292740,
    uf="BA",
)

MUNICIPIOS: dict[str, MunicipioSpec] = {
    SALVADOR.slug: SALVADOR,
    str(SALVADOR.id_municip): SALVADOR,
}


def resolve_municipio(value: str) -> MunicipioSpec:
    key = value.strip().lower()
    if key in MUNICIPIOS:
        return MUNICIPIOS[key]
    if value.strip().isdigit() and value.strip() in MUNICIPIOS:
        return MUNICIPIOS[value.strip()]
    known = ", ".join(sorted({m.slug for m in MUNICIPIOS.values()}))
    raise ValueError(f"Município desconhecido: {value!r}. Opções: {known}")
