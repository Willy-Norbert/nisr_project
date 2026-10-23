import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import { useEffect, useMemo } from 'react'
import { GeoJSON, MapContainer, useMap } from 'react-leaflet'
import type { GeoFeatureProps } from '../lib/api'

export const BLUES = ['#dbe9f6', '#a9cbea', '#6aa6d9', '#2f7fc4', '#005baa', '#003c73']
export const REDS = ['#fde7e3', '#f8b9ad', '#ef8a78', '#dc5a48', '#b8352a', '#8a2219']

type Geo = FeatureCollection<Geometry, GeoFeatureProps>

function quantileBreaks(values: number[], classes: number): number[] {
  const sorted = [...values].sort((a, b) => a - b)
  return Array.from({ length: classes - 1 }, (_, i) => sorted[Math.floor(((i + 1) / classes) * (sorted.length - 1))])
}

function FitBounds({ geo }: { geo: Geo }) {
  const map = useMap()
  useEffect(() => {
    const bounds = L.geoJSON(geo).getBounds()
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [10, 10] })
  }, [geo, map])
  return null
}

export default function DistrictMap({ geo, label, format, selected, onSelect, palette = BLUES, height = 470 }: {
  geo: Geo
  label: string
  format: (v: number | null) => string
  selected?: string | null
  onSelect?: (district: string) => void
  palette?: string[]
  height?: number
}) {
  const values = useMemo(
    () => geo.features.map((f) => f.properties.value).filter((v): v is number => v !== null),
    [geo],
  )
  const breaks = useMemo(() => (values.length ? quantileBreaks(values, palette.length) : []), [values, palette])
  const color = (v: number | null) => {
    if (v === null) return '#e9edf1'
    const idx = breaks.findIndex((b) => v <= b)
    return palette[idx === -1 ? palette.length - 1 : idx]
  }

  const key = useMemo(() => JSON.stringify(geo.features.map((f) => f.properties.value)) + (selected ?? ''), [geo, selected])

  const style = (feature?: Feature<Geometry, GeoFeatureProps>) => {
    const p = feature!.properties
    const isSel = selected && p.district === selected
    return {
      fillColor: color(p.value),
      fillOpacity: 0.92,
      color: isSel ? '#f5b800' : '#ffffff',
      weight: isSel ? 3.5 : 1.2,
    }
  }

  const onEach = (feature: Feature<Geometry, GeoFeatureProps>, layer: L.Layer) => {
    const p = feature.properties
    layer.bindTooltip(
      `<div class="map-tooltip"><strong>${p.district}</strong> · ${p.province}<br/>${label}: <b>${format(p.value)}</b>` +
        (p.low_reliability ? '<br/><em>Low sample size</em>' : '') +
        '</div>',
      { sticky: true },
    )
    layer.on({
      mouseover: (e) => (e.target as L.Path).setStyle({ weight: 3, color: '#003c73' }),
      mouseout: (e) => (e.target as L.Path).setStyle(style(feature)),
      click: () => onSelect?.(p.district),
    })
  }

  const min = values.length ? Math.min(...values) : null
  const max = values.length ? Math.max(...values) : null

  return (
    <div className="map-card">
      <MapContainer className="map" style={{ height }} center={[-1.94, 29.87]} zoom={8} zoomSnap={0.25}
        scrollWheelZoom={false} attributionControl={false}>
        <GeoJSON key={key} data={geo} style={style} onEachFeature={onEach} />
        <FitBounds geo={geo} />
      </MapContainer>
      <div className="map-legend">
        <strong>{label}</strong>
        <div className="legend-scale">{palette.map((c) => <span key={c} style={{ background: c }} />)}</div>
        <div className="legend-labels"><span>{format(min)}</span><span>{format(max)}</span></div>
      </div>
    </div>
  )
}
