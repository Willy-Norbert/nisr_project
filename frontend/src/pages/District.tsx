import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import DistrictFocusMap from '../components/DistrictFocusMap'
import { GroupedBars, TrendChart } from '../components/charts'
import { Icon } from '../components/Icons'
import type { IconName } from '../components/Icons'
import { ErrorBox, Field, Loader, Note, PageHero, Select } from '../components/ui'
import { qs } from '../lib/api'
import type { DistrictProfile, Filters, Priorities, ScenarioResult, Season, SeasonSeries } from '../lib/api'
import { decimals, num, signed, valueWithUnit } from '../lib/format'
import { useApi } from '../lib/useApi'

const GLANCE: { id: string; icon: IconName }[] = [
  { id: 'yield_kg_ha', icon: 'sprout' },
  { id: 'improved_seed_pct', icon: 'seed' },
  { id: 'inorganic_fertilizer_pct', icon: 'flask' },
  { id: 'extension_access_pct', icon: 'users' },
]

export default function District() {
  const { name = '' } = useParams()
  const navigate = useNavigate()
  const filters = useApi<Filters>('/metadata/filters')
  const [year, setYear] = useState(2025)
  const [season, setSeason] = useState<Season>('A')

  useEffect(() => {
    if (filters.data) {
      setYear(filters.data.latest.year)
      setSeason(filters.data.latest.season)
    }
  }, [filters.data])

  const profile = useApi<DistrictProfile>(`/geography/locations/${encodeURIComponent(name)}${qs({ year, season })}`)
  const trend = useApi<SeasonSeries>(`/comparisons/seasons${qs({ indicator_id: 'yield_kg_ha', crop: 'Maize', level: 'district', area: name })}`)
  const priorities = useApi<Priorities>(`/priorities${qs({ crop: 'Maize', year, season })}`)
  const scenario = useApi<ScenarioResult>(`/scenarios${qs({ crop: 'Maize', district: name, season: season === 'C' ? 'A' : season, inputs: ['improved_seed', 'inorganic_fertilizer'] })}`)

  const p = profile.data
  const priority = priorities.data?.districts.find((d) => d.district === p?.district)
  const byId = (id: string) => p?.indicators.find((r) => r.indicator_id === id)

  return (
    <>
      <PageHero crumb={p?.district ?? name} title={`${p?.district ?? name} District`}
        lead={p ? `${p.province} Province · how the district compares with Rwanda on yields, inputs and support services, ${year} Season ${season}.` : undefined} />

      <section className="section section--alt" style={{ paddingTop: 28 }}>
        <div className="container stack">
          {profile.error && <ErrorBox message={profile.error} />}

          <div className="toolbar">
            <Field label="District">
              <select className="select" value={p?.district ?? name} onChange={(e) => navigate(`/districts/${encodeURIComponent(e.target.value)}`)}>
                {(filters.data?.districts ?? [name]).map((d) => <option key={d}>{d}</option>)}
              </select>
            </Field>
            {filters.data && (
              <>
                <Field label="Year"><Select value={year} onChange={setYear} options={filters.data.years} /></Field>
                <Field label="Season"><Select value={season} onChange={setSeason} options={filters.data.seasons} format={(s) => `Season ${s}`} /></Field>
              </>
            )}
            <div className="spacer" />
            <Link className="btn btn-outline" to={`/explore?q=${encodeURIComponent(`Tell me about ${p?.district ?? name} district`)}`}><Icon name="chat" size={16} /> Ask about it</Link>
            <Link className="btn btn-primary" to={`/reports?district=${encodeURIComponent(p?.district ?? name)}`}><Icon name="download" size={16} /> District report</Link>
          </div>

          <div className="grid district-top">
            <div className="card" style={{ overflow: 'hidden' }}>
              <div className="card-head"><h3>District map</h3><small>Click the Rwanda inset to open another district</small></div>
              <DistrictFocusMap district={p?.district ?? name} height={430} />
            </div>

            <div className="stack" style={{ gap: 16 }}>
              <div className="grid grid-2" style={{ gap: 16 }}>
                {GLANCE.map((g) => {
                  const r = byId(g.id)
                  return (
                    <div key={g.id} className="kpi kpi--left">
                      <div className="kpi-icon"><Icon name={g.icon} size={26} /></div>
                      <div className="kpi-label">{r ? `${r.name}${r.crop ? ` (${r.crop.toLowerCase()})` : ''}` : '…'}</div>
                      <div className="kpi-value">{r ? valueWithUnit(r.value, r.unit) : '–'}</div>
                      {r && (
                        <div className="kpi-meta">
                          Rwanda {valueWithUnit(r.national_value, r.unit)}{r.rank && <> · rank <strong>{r.rank}</strong>/{r.of}</>}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
              <div className="card card-pad district-callout">
                <span className="article-tag">Maize priority score</span>
                {priority ? (
                  <>
                    <div className="row" style={{ alignItems: 'baseline' }}>
                      <strong className="callout-big">#{priority.rank}</strong>
                      <span className="muted">of {priorities.data?.districts.length} districts · score {num(priority.score, 1)}</span>
                    </div>
                    <p className="small" style={{ margin: 0 }}>
                      {priority.rank <= 8 ? 'A high-priority district for maize support.' : priority.rank <= 20 ? 'A mid-priority district for maize support.' : 'A lower-priority district for maize support.'}{' '}
                      <Link to="/priorities">How the score works</Link>
                    </p>
                  </>
                ) : priorities.loading ? <Loader /> : <p className="small muted" style={{ margin: 0 }}>Not enough maize plots to score this district.</p>}
                {scenario.data && (
                  <p className="small" style={{ margin: '10px 0 0' }}>
                    If all maize plots used improved seed and fertilizer, the model estimates yields would change by{' '}
                    <strong style={{ color: 'var(--green)' }}>{signed(scenario.data.change_pct)}</strong>{' '}
                    (model baseline {num(scenario.data.current_yield)} → {num(scenario.data.scenario_yield)} kg/ha, {scenario.data.year} Season {scenario.data.season}).
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <div className="card-head"><h3>Crop yields vs Rwanda</h3><small>kg/ha · {year} Season {season}</small></div>
              <div className="card-body">
                {p ? (p.crop_yields.length ? (
                  <GroupedBars unit="kg/ha" keys={['district', 'rwanda']} labels={[p.district, 'Rwanda']} height={320}
                    data={p.crop_yields.map((c) => ({ name: c.crop, district: c.value, rwanda: c.national_value }))} />
                ) : <p className="empty">No crop has enough plots this season.</p>) : <Loader />}
              </div>
            </div>
            <div className="card">
              <div className="card-head"><h3>Maize yield across seasons</h3><small>kg/ha · {p?.district ?? name}</small></div>
              <div className="card-body">
                {trend.data?.series.length ? <TrendChart data={trend.data.series} unit="kg/ha" height={320} />
                  : trend.loading ? <Loader /> : <p className="empty">No maize trend for this district.</p>}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h3>All indicators</h3><small>Rank 1 = best of all districts</small></div>
            <div className="table-wrap">
              {p ? (
                <table className="table">
                  <thead><tr><th>Indicator</th><th className="num">{p.district}</th><th className="num">Rwanda</th><th className="num">Difference</th><th className="num">Rank</th></tr></thead>
                  <tbody>
                    {p.indicators.map((r) => {
                      const good = r.difference !== null && (r.higher_is_better ? r.difference >= 0 : r.difference <= 0)
                      return (
                        <tr key={r.indicator_id}>
                          <td>{r.name}{r.crop && <span className="muted small"> ({r.crop})</span>}</td>
                          <td className="num"><strong>{valueWithUnit(r.value, r.unit)}</strong></td>
                          <td className="num">{valueWithUnit(r.national_value, r.unit)}</td>
                          <td className="num" style={{ color: r.difference === null ? undefined : good ? 'var(--green)' : 'var(--red)' }}>
                            {r.difference === null ? '–' : signed(r.difference, decimals(r.unit), r.unit.startsWith('%') ? ' pts' : '')}
                          </td>
                          <td className="num">{r.rank ? `${r.rank} / ${r.of}` : '–'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              ) : <Loader />}
            </div>
          </div>

          <Note>Household indicators (extension, cooperatives, insurance, support) come from the Agriculture Household Survey 2024. Crop-specific indicators use maize unless stated.</Note>
        </div>
      </section>
    </>
  )
}
