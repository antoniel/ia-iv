"""Recorte territorial do pipeline ML."""

from __future__ import annotations

from dataclasses import dataclass

from ml.config import UF_IBGE


@dataclass(frozen=True, slots=True)
class RegionSpec:
    slug: str
    name: str
    uf: str

    @property
    def uf_code(self) -> int:
        return UF_IBGE[self.uf.upper()]


BA = RegionSpec(slug="ba", name="Bahia", uf="BA")

REGIONS: dict[str, RegionSpec] = {
    BA.slug: BA,
    BA.uf.lower(): BA,
    BA.uf.upper(): BA,
}


def resolve_region(value: str) -> RegionSpec:
    key = value.strip().lower()
    if key in REGIONS:
        return REGIONS[key]
    known = ", ".join(sorted({r.slug for r in REGIONS.values()}))
    raise ValueError(f"Região desconhecida: {value!r}. Opções: {known}")
