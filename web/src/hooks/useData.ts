import { useEffect, useState } from "react";
import type { FeatureCollection } from "geojson";
import { fetchRegionGeo, fetchRegionMunicipios } from "../api";
import type { MunicipioCount } from "../types";

export function useRegionData(ano: number) {
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [municipios, setMunicipios] = useState<MunicipioCount[]>([]);
  const [ufs, setUfs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([fetchRegionGeo(ano), fetchRegionMunicipios(ano)])
      .then(([g, m]) => {
        if (cancelled) return;
        setGeo(g.geo);
        setMunicipios(m.municipios);
        setUfs(g.ufs);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ano]);

  return { geo, municipios, ufs, loading, error };
}
