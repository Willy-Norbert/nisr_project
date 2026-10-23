import type { FeatureCollection, Geometry } from 'geojson'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import DistrictMap from '../components/DistrictMap'
import { RankingBars, TrendChart } from '../components/charts'
import { Icon } from '../components/Icons'
import { ErrorBox, Field, Loader, Note, PageHero, ReliabilityBadge, Select } from '../components/ui'
import { qs } from '../lib/api'
import type { DistrictComparison, Filters, GeoFeatureProps, IndicatorDef, Season, SeasonSeries } from '../lib/api'
import { decimals, num, valueWithUnit } from '../lib/format'
import { useApi } from '../lib/useApi'

const ALL = 'All crops'

export default function Dashboard() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const filters = useApi<Filters>('/metadata/filters')
  const indicators = useApi<IndicatorDef[]>('/indicators')

  const [indicatorId, setIndicatorId] = useState(params.get('indicator') ?? 'yield_kg_ha')
  const [crop, setCrop] = useState(params.get('crop') ?? 'Maize')
  const [year, setYear] = useState<number>(2025)
  const [season, setSeason] = useState<Season>('A')

  const def = indicators.data?.find((i) => i.id === indicatorId)
  const household = def?.source.includes('Household') ?? false
  const effectiveCrop = household ? ALL : def?.crop_specific && crop === ALL ? 'Maize' : crop
  const openDistrict = (d: string) => navigate(`/districts/${encodeURIComponent(d)}`)

  useEffect(() => {
    if (filters.data) {
      setYear(filters.data.latest.year)
      setSeason(filters.data.latest.season)
    }
  }, [filters.data])

  const query = qs({ indicator_id: indicatorId, year, season, crop: effectiveCrop })
  const geo = useApi<FeatureCollection<Geometry, GeoFeatureProps>>(`/geography/districts.geojson${query}`)
  const comparison = useApi<DistrictComparison>(`/comparisons/districts${query}`)
  const trend = useApi<SeasonSeries>(`/comparisons/seasons${qs({ indicator_id: indicatorId, crop: effectiveCrop, level: 'national', area: 'Rwanda' })}`)

  const unit = def?.unit ?? ''
  const fmt = (v: number | null) => (v === null ? 'No data' : valueWithUnit(v, unit))
  const cropOptions = useMemo(() => {
    const crops = filters.data?.crops ?? [ALL]
    return def?.crop_specific ? crops.filter((c) => c !== ALL) : crops
  }, [filters.data, def])

  return (
    <>
      <PageHero crumb="Dashboard" title="District dashboard"
        lead="Map any indicator across Rwanda's 30 districts. Click a district on the map or in the ranking to open its page with a local map and full profile." />

      <section className="section section--alt" style={{ paddingTop: 28 }}>
        <div className="container stack">
          {(filters.error || indicators.error) && <ErrorBox message={filters.error ?? indicators.error ?? ''} />}

          <div className="toolbar">
            <Field label="Indicator">
              <select className="select" value={indicatorId} onChange={(e) => setIndicatorId(e.target.value)} style={{ minWidth: 240 }}>
                {['production', 'inputs', 'practices', 'support', 'sustainability'].map((topic) => (
                  <optgroup key={topic} label={topic[0].toUpperCase() + topic.slice(1)}>
                    {indicators.data?.filter((i) => i.topic === topic).map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
                  </optgroup>
                ))}
              </select>
            </Field>
            <Field label="Crop">
              <select className="select" value={effectiveCrop} disabled={household} onChange={(e) => setCrop(e.target.value)}>
                {cropOptions.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            {!household && filters.data && (
              <>
                <Field label="Year"><Select value={year} onChange={setYear} options={filters.data.years} /></Field>
                <Field label="Season"><Select value={season} onChange={setSeason} options={filters.data.seasons} format={(s) => `Season ${s}`} /></Field>
              </>
            )}
            <div className="spacer" />
            {comparison.data?.national_value != null && (
              <div style={{ textAlign: 'right' }}>
                <div className="small muted">Rwanda</div>
                <div style={{ fontFamily: 'var(--font-head)', fontSize: 24, fontWeight: 700, color: 'var(--blue)' }}>{fmt(comparison.data.national_value)}</div>
              </div>
            )}
          </div>

          {def && (
            <Note>
              <strong>{def.name}</strong>: {def.description} {household ? 'Source: Agriculture Household Survey 2024 (Season A).' : `Source: Seasonal Agricultural Survey, ${year} Season ${season}.`}
            </Note>
          )}

          <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.5fr) minmax(0, 1fr)' }}>
            <div className="card" style={{ overflow: 'hidden' }}>
              <div className="card-head">
                <h3>{def?.name ?? 'Indicator'}{def && !household && effectiveCrop !== ALL ? ` · ${effectiveCrop}` : ''}</h3>
                <small>{household ? '2024 household survey' : `${year} Season ${season}`}</small>
              </div>
              {geo.loading && !geo.data && <Loader />}
              {geo.data && <DistrictMap geo={geo.data} label={def?.name ?? ''} format={fmt} onSelect={openDistrict} />}
            </div>

            <div className="card">
              <div className="card-head"><h3>District ranking</h3><small>Click a district to open it</small></div>
              <div className="card-body" style={{ maxHeight: 470, overflowY: 'auto', padding: 0 }}>
                <table className="table">
                  <thead><tr><th>#</th><th>District</th><th>Value</th></tr></thead>
                  <tbody>
                    {comparison.data?.districts.map((d) => (
                      <tr key={d.area} onClick={() => openDistrict(d.area)} style={{ cursor: 'pointer' }}>
                        <td><span className={`rank${d.rank <= 3 ? ' top' : ''}`}>{d.rank}</span></td>
                        <td><Link to={`/districts/${encodeURIComponent(d.area)}`}><strong>{d.area}</strong></Link> <span className="muted small">{d.province}</span> <ReliabilityBadge low={d.low_reliability} /></td>
                        <td className="num">{num(d.value, decimals(unit))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <div className="card-head"><h3>All districts compared</h3><small>Dashed line: Rwanda</small></div>
              <div className="card-body">
                {comparison.data ? (
                  <RankingBars data={comparison.data.districts.map((d) => ({ name: d.area, value: d.value }))}
                    national={comparison.data.national_value} unit={unit} />
                ) : <Loader />}
              </div>
            </div>
            <div className="card" style={{ alignSelf: 'start' }}>
              <div className="card-head"><h3>Trend across seasons</h3><small>Rwanda</small></div>
              <div className="card-body">
                {trend.data?.series.length ? <TrendChart data={trend.data.series} unit={unit} height={300} />
                  : trend.loading ? <Loader /> : <p className="empty">Only one survey period is available for this indicator.</p>}
                <div className="note" style={{ marginTop: 12 }}>
                  <Icon name="info" size={16} />
                  <div>Season A (Sep–Feb) is the main season, Season B (Mar–Jun) the second, and Season C (Jul–Sep) the dry season, mostly marshlands.</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
