import type { FeatureCollection, Geometry } from 'geojson'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import DistrictMap, { REDS } from '../components/DistrictMap'
import { ErrorBox, Field, Loader, Note, PageHero, Select } from '../components/ui'
import { qs } from '../lib/api'
import type { Filters, GeoFeatureProps, Priorities as PrioritiesData, Season } from '../lib/api'
import { compact, num } from '../lib/format'
import { useApi } from '../lib/useApi'

const DEFAULT_WEIGHTS: Record<string, number> = { yield_gap: 30, potential_gain: 30, seed_gap: 15, fertilizer_gap: 15, extension_gap: 10 }

export default function Priorities() {
  const filters = useApi<Filters>('/metadata/filters')
  const [crop, setCrop] = useState('Maize')
  const [year, setYear] = useState(2025)
  const [season, setSeason] = useState<Season>('A')
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS)
  const [debounced, setDebounced] = useState(DEFAULT_WEIGHTS)
  const navigate = useNavigate()
  const openDistrict = (d: string) => navigate(`/districts/${encodeURIComponent(d)}`)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(weights), 300)
    return () => clearTimeout(t)
  }, [weights])

  const query = qs({
    crop, year, season,
    ...Object.fromEntries(Object.entries(debounced).map(([k, v]) => [`w_${k}`, v / 100])),
  })
  const data = useApi<PrioritiesData>(`/priorities${query}`)
  const base = useApi<FeatureCollection<Geometry, GeoFeatureProps>>('/geography/districts.geojson')

  const geo = useMemo(() => {
    if (!base.data || !data.data) return null
    const scores = new Map(data.data.districts.map((d) => [d.district, d]))
    return {
      ...base.data,
      features: base.data.features.map((f) => {
        const d = scores.get(f.properties.district)
        return { ...f, properties: { ...f.properties, value: d ? d.score : null } }
      }),
    }
  }, [base.data, data.data])

  const crops = (filters.data?.crops ?? []).filter((c) => c !== 'All crops')
  const pr = data.data

  return (
    <>
      <PageHero crumb="Priorities" title="Priority districts"
        lead="A transparent score showing where support for a crop could close the largest yield gaps. Adjust the weights to reflect your programme's goals." />
      <section className="section section--alt" style={{ paddingTop: 28 }}>
        <div className="container stack">
          {filters.error && <ErrorBox message={filters.error} />}
          <div className="toolbar">
            <Field label="Crop"><Select value={crop} onChange={setCrop} options={crops.length ? crops : ['Maize']} /></Field>
            {filters.data && (
              <>
                <Field label="Year"><Select value={year} onChange={setYear} options={filters.data.years} /></Field>
                <Field label="Season"><Select value={season} onChange={setSeason} options={['A', 'B'] as Season[]} format={(s) => `Season ${s}`} /></Field>
              </>
            )}
            <div className="spacer" />
            {pr?.benchmark_yield_kg_ha && (
              <div style={{ textAlign: 'right' }}>
                <div className="small muted">Benchmark (top 10% of districts)</div>
                <div style={{ fontFamily: 'var(--font-head)', fontSize: 22, fontWeight: 600, color: 'var(--blue)' }}>{num(pr.benchmark_yield_kg_ha)} kg/ha</div>
              </div>
            )}
          </div>

          <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.4fr)' }}>
            <div className="card">
              <div className="card-head"><h3>Score weights</h3><button className="btn btn-outline btn-sm" onClick={() => setWeights(DEFAULT_WEIGHTS)}>Reset</button></div>
              <div className="card-body stack" style={{ gap: 16 }}>
                {(pr?.components ?? []).map((c) => (
                  <div key={c.id}>
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                      <span className="small"><strong>{c.label}</strong></span>
                      <span className="badge">{weights[c.id]}%</span>
                    </div>
                    <input className="range" type="range" min={0} max={60} step={5} value={weights[c.id]}
                      onChange={(e) => setWeights((w) => ({ ...w, [c.id]: Number(e.target.value) }))} />
                  </div>
                ))}
                {pr && <Note>{pr.method}</Note>}
              </div>
            </div>
            <div className="card" style={{ overflow: 'hidden' }}>
              <div className="card-head"><h3>Priority score · {crop}</h3><small>Darker = higher priority</small></div>
              {geo ? <DistrictMap geo={geo} label="Priority score" format={(v) => (v === null ? 'No data' : `${num(v, 1)} / 100`)}
                palette={REDS} onSelect={openDistrict} height={520} /> : <Loader />}
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h3>Ranking and score components</h3><small>{pr ? `${pr.year} Season ${pr.season}` : ''}</small></div>
            <div className="table-wrap">
              {data.loading && !pr && <Loader />}
              {data.error && <div className="card-body"><ErrorBox message={data.error} /></div>}
              {pr && (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Rank</th><th>District</th><th>Score</th><th className="num">Yield (kg/ha)</th><th className="num">Improved seed</th>
                      <th className="num">Fertilizer</th><th className="num">Extension</th><th className="num">Est. gain</th><th className="num">Extra production</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pr.districts.map((d) => (
                      <tr key={d.district} onClick={() => openDistrict(d.district)} style={{ cursor: 'pointer' }}>
                        <td><span className={`rank${d.rank <= 5 ? ' top' : ''}`}>{d.rank}</span></td>
                        <td><Link to={`/districts/${encodeURIComponent(d.district)}`}><strong>{d.district}</strong></Link> <span className="muted small">{d.province}</span></td>
                        <td>
                          <div className="bar-cell"><div className="bar-track"><div className="bar-fill" style={{ width: `${d.score}%`, background: '#c4372d' }} /></div>
                            <strong className="small">{num(d.score, 1)}</strong></div>
                        </td>
                        <td className="num">{num(d.yield_kg_ha)}</td>
                        <td className="num">{num(d.improved_seed_pct, 1)}%</td>
                        <td className="num">{num(d.inorganic_fertilizer_pct, 1)}%</td>
                        <td className="num">{d.extension_access_pct == null ? '–' : `${num(d.extension_access_pct, 1)}%`}</td>
                        <td className="num" style={{ color: 'var(--green)', fontWeight: 600 }}>{d.potential_gain_pct == null ? '–' : `+${num(d.potential_gain_pct, 1)}%`}</td>
                        <td className="num">{d.additional_production_t == null ? '–' : `${compact(d.additional_production_t)} t`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
