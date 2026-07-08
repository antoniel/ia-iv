"""Recorte territorial do pipeline ML."""

from __future__ import annotations

from dataclasses import dataclass

from ml.config import UF_IBGE

# Mesma ordem do backend / scripts/build_nordeste.py
NORDESTE_UFS: tuple[str, ...] = ("MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA")


@dataclass(frozen=True, slots=True)
class RegionSpec:
    slug: str
    name: str
    ufs: tuple[str, ...]

    @property
    def uf(self) -> str:
        """Compat mono-UF: primeira (ou única) sigla."""
        return self.ufs[0]

    @property
    def uf_code(self) -> int:
        return UF_IBGE[self.ufs[0].upper()]

    @property
    def uf_codes(self) -> frozenset[int]:
        return frozenset(UF_IBGE[u.upper()] for u in self.ufs)

    @property
    def is_multi_uf(self) -> bool:
        return len(self.ufs) > 1


BA = RegionSpec(slug="ba", name="Bahia", ufs=("BA",))
NE = RegionSpec(slug="ne", name="Nordeste", ufs=NORDESTE_UFS)

REGIONS: dict[str, RegionSpec] = {
    BA.slug: BA,
    BA.uf.lower(): BA,
    BA.uf.upper(): BA,
    NE.slug: NE,
    "nordeste": NE,
    "ne": NE,
}


def resolve_region(value: str) -> RegionSpec:
    key = value.strip().lower()
    if key in REGIONS:
        return REGIONS[key]
    known = ", ".join(sorted({r.slug for r in REGIONS.values()}))
    raise ValueError(f"Região desconhecida: {value!r}. Opções: {known}")
