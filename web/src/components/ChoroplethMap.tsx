import type { Feature, FeatureCollection, Geometry } from "geojson"
import type { Layer, PathOptions } from "leaflet"
import L from "leaflet"
import { useEffect, useMemo } from "react"
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet"
import { CLUSTER_NOMES, type MunicipioCount } from "../types"

type Props = {
  geo: FeatureCollection
  counts: MunicipioCount[]
  valueKey?: "notificacoes" | "cluster"
  clusterColors?: readonly string[]
  mapKey?: string | number
}

function FitBounds({ geo }: { geo: FeatureCollection }) {
  const map = useMap()
  useEffect(() => {
    if (!geo.features.length) return
    const layer = L.geoJSON(geo as unknown as GeoJSON.GeoJsonObject)
    const bounds = layer.getBounds()
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [24, 24] })
    }
  }, [geo, map])
  return null
}

function choroplethStyle(
  value: number,
  max: number,
  mode: "count" | "cluster",
  clusterColors?: readonly string[],
): PathOptions {
  if (mode === "cluster") {
    const c = clusterColors?.[value] ?? clusterColors?.[0] ?? "#1b7837"
    return {
      fillColor: c,
      color: "#000",
      weight: 0.4,
      opacity: 0.8,
      fillOpacity: 0.92,
    }
  }
  const t = max > 0 ? value / max : 0
  const r = Math.round(255 * t)
  const g = Math.round(240 - 180 * t)
  const b = Math.round(200 - 160 * t)
  return {
    fillColor: `rgb(${r},${g},${b})`,
    color: "#444",
    weight: 0.7,
    fillOpacity: 0.85,
  }
}

export default function ChoroplethMap({ geo, counts, valueKey = "notificacoes", clusterColors, mapKey }: Props) {
  const lookup = useMemo(() => {
    const m = new Map<string, MunicipioCount & { cluster?: number }>()
    for (const row of counts) {
      m.set(row.codarea, row)
    }
    return m
  }, [counts])

  const max = useMemo(() => Math.max(...counts.map((c) => c.notificacoes), 1), [counts])

  const mode = valueKey === "cluster" ? "cluster" : "count"

  const style = (feat: Feature<Geometry> | undefined) => {
    const ca = String((feat?.properties as { codarea?: string })?.codarea ?? "")
    const row = lookup.get(ca)
    const val = valueKey === "cluster" ? ((row as { cluster?: number })?.cluster ?? 0) : (row?.notificacoes ?? 0)
    return choroplethStyle(val, max, mode, clusterColors)
  }

  const onEach = (feat: Feature<Geometry>, layer: Layer) => {
    const ca = String((feat.properties as { codarea?: string }).codarea ?? "")
    const row = lookup.get(ca)
    const uf = row?.uf ?? (feat.properties as { uf?: string }).uf ?? ""
    const nome = row?.municipio ?? ca
    const clusterVal = (row as { cluster?: number })?.cluster ?? 0
    const casosSemana = (row as { casosSemana?: number })?.casosSemana ?? 0
    const clusterName = CLUSTER_NOMES[clusterVal] ?? `Grupo ${clusterVal + 1}`
    const label =
      valueKey === "cluster"
        ? `Cluster ${clusterVal} — ${clusterName}<br/>${casosSemana.toLocaleString("pt-BR")} ocorrências na semana`
        : `Notificações: ${row?.notificacoes?.toLocaleString("pt-BR") ?? 0}`
    const prefix = uf ? `<small>${uf}</small><br/>` : ""
    layer.bindTooltip(`${prefix}<b>${nome}</b><br/>${label}`)
  }

  return (
    <MapContainer center={[-8, -41]} zoom={5} className="map-wrap" scrollWheelZoom={false}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds geo={geo} />
      <GeoJSON key={mapKey ?? valueKey} data={geo} style={style} onEachFeature={onEach} />
    </MapContainer>
  )
}
