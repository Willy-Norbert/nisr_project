import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Banner } from '../components/Banner'
import { Icon } from '../components/Icons'
import type { IconName } from '../components/Icons'
import { Delta, ErrorBox, Kpi, Loader } from '../components/ui'
import type { Insight, Overview } from '../lib/api'
import { valueWithUnit } from '../lib/format'
import { useApi } from '../lib/useApi'

const KPI_ICONS: Record<string, IconName> = {
  improved_seed_pct: 'seed',
  inorganic_fertilizer_pct: 'flask',
  irrigation_pct: 'drop',
  extension_access_pct: 'users',
}

const QUICK = [
  'Tell me about Rwanda',
  'Which districts have the highest maize yield?',
  'Does improved seed increase maize yield?',
]

const POSTERS: { to: string; year: string; title: string; sub: string; foot: string }[] = [
  { to: '/explore', year: 'Ask', title: 'THE DATA', sub: 'Plain-language questions, answered with official statistics', foot: 'Start exploring' },
  { to: '/dashboard', year: '30', title: 'DISTRICTS MAPPED', sub: '13 indicators by crop, season and year', foot: 'Open the dashboard' },
  { to: '/priorities', year: 'Where', title: 'TO ACT FIRST', sub: 'Priority districts for each crop, with a transparent score', foot: 'See priorities' },
]

export default function Home() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const overview = useApi<Overview>('/overview')
  const insights = useApi<Insight[]>('/insights')

  const ask = (question: string) => navigate(`/explore?q=${encodeURIComponent(question)}`)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (q.trim()) ask(q.trim())
  }

  const ov = overview.data
  return (
    <>
      <Banner>
        <p className="banner-tagline">
          Analiza turns NISR agricultural surveys into evidence for closing Rwanda's crop yield gaps,
          district by district and season by season.
        </p>
        <form className="askbox" onSubmit={submit}>
          <Icon name="search" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about yields, inputs or a district…" aria-label="Ask a question" />
          <button className="btn btn-primary" type="submit">Ask</button>
        </form>
        <div className="chips">
          {QUICK.map((s) => <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>)}
        </div>
      </Banner>

      <section className="band band--blue band--posters">
        <div className="container grid grid-3">
          {POSTERS.map((p) => (
            <Link key={p.to} to={p.to} className="poster">
              <div className="poster-art">
                <span className="poster-kicker">Analiza</span>
                <strong className="poster-year">{p.year}</strong>
                <strong className="poster-title">{p.title}</strong>
                <span className="poster-sub">{p.sub}</span>
              </div>
              <div className="poster-foot">
                <span>{p.foot}</span>
                <Icon name="chevronRight" size={14} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="band band--light">
        <div className="container">
          <div className="band-head">
            <h2 className="band-title">Key figures{ov ? ` · ${ov.year} Season ${ov.season}` : ''}</h2>
            <Link to="/dashboard" className="btn-line">View figures <Icon name="chevronRight" size={13} /></Link>
          </div>
          <p className="band-lead muted">National estimates, weighted to represent all farm plots and households.</p>
          {overview.loading && <Loader />}
          {overview.error && <ErrorBox message={overview.error} />}
          {ov && (
            <div className="grid grid-4">
              {ov.kpis.map((k) => (
                <Kpi key={k.indicator_id} icon={KPI_ICONS[k.indicator_id] ?? 'chart'} label={k.name} value={valueWithUnit(k.value, k.unit)}
                  meta={<>{k.period}{k.change !== null && <> · <Delta value={k.change} suffix=" pts" /></>}</>} />
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="band band--texture">
        <div className="container">
          <div className="band-head">
            <h2 className="band-title">Latest findings</h2>
            <Link to="/insights" className="btn-line">All insights <Icon name="chevronRight" size={13} /></Link>
          </div>
          {insights.loading && <Loader />}
          {insights.data && (
            <div className="releases">
              {insights.data.slice(0, 4).map((i) => (
                <Link key={i.id} to={`/insights#${i.id}`} className="release">
                  <h4>{i.title}</h4>
                  <div className="release-date">{i.period} · {i.topic}</div>
                  <p>{i.summary}</p>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>
    </>
  )
}
