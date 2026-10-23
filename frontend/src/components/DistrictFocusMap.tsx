import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import { useEffect, useMemo } from 'react'
import { GeoJSON, MapContainer, useMap } from 'react-leaflet'
import { useNavigate } from 'react-router-dom'
import type { GeoFeatureProps } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Loader } from './ui'

type Geo = FeatureCollection<Geometry, GeoFeatureProps>

function Fit({ data, padding }: { data: Geo; padding: number }) {
  const map = useMap()
  useEffect(() => {
    const bounds = L.geoJSON(data).getBounds()
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [padding, padding] })
  }, [data, padding, map])
  return null
}

const STATIC = { zoomControl: false, dragging: false, scrollWheelZoom: false, doubleClickZoom: false, touchZoom: false, boxZoom: false, keyboard: false, attributionControl: false }

/** One district drawn on its own, with a small Rwanda locator map; clicking a district in the locator opens it. */
export default function DistrictFocusMap({ district, height = 380 }: { district: string; height?: number }) {
  const navigate = useNavigate()
  const geo = useApi<Geo>('/geography/districts.geojson')

  const own = useMemo<Geo | null>(
    () => (geo.data ? { ...geo.data, features: geo.data.features.filter((f) => f.properties.district === district) } : null),
    [geo.data, district],
  )
  if (!geo.data || !own) return <Loader label="Loading map…" />
  const province = own.features[0]?.properties.province

  const locatorStyle = (feature?: Feature<Geometry, GeoFeatureProps>) =>
    feature!.properties.district === district
      ? { fillColor: '#0057a8', fillOpacity: 1, color: '#0057a8', weight: 1 }
      : { fillColor: '#dfe6ee', fillOpacity: 1, color: '#ffffff', weight: 0.6 }

  const onLocator = (feature: Feature<Geometry, GeoFeatureProps>, layer: L.Layer) => {
    const p = feature.properties
    layer.bindTooltip(p.district, { sticky: true })
    layer.on({ click: () => p.district !== district && navigate(`/districts/${encodeURIComponent(p.district)}`) })
  }

  return (
    <div className="map-card district-focus" style={{ height }}>
      <MapContainer key={district} className="map" style={{ height }} center={[-1.94, 29.87]} zoom={9} zoomSnap={0.1} {...STATIC}>
        <GeoJSON key={district} data={own} style={{ fillColor: '#0057a8', fillOpacity: 0.9, color: '#12263f', weight: 2 }} />
        <Fit data={own} padding={28} />
      </MapContainer>
      <div className="district-focus-name">
        <strong>{district}</strong>
        {province && <span>{province} Province</span>}
      </div>
      <div className="district-locator" title="Location in Rwanda">
        <MapContainer key={`loc-${district}`} style={{ height: '100%', width: '100%' }} center={[-1.94, 29.87]} zoom={6} zoomSnap={0.1} {...STATIC}>
          <GeoJSON key={`loc-${district}`} data={geo.data} style={locatorStyle} onEachFeature={onLocator} />
          <Fit data={geo.data} padding={4} />
        </MapContainer>
        <span>Rwanda</span>
      </div>
    </div>
  )
}
