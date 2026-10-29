import { Icon } from '../components/Icons'
import { ErrorBox, Loader, PageHero, SectionHead } from '../components/ui'
import type { IndicatorDef } from '../lib/api'
import { num } from '../lib/format'
import { useApi } from '../lib/useApi'

interface Methodology {
  generated_at: string
  coverage: { seasons: { year: number; season: string; plot_crop_rows: number }[]; plot_crop_records: number; households: number }
  crops: string[]
  model: { r2_log_yield: number; mape_yield: number; train_rows: number; test_rows: number; model: string; features: string[] }
  notes: string[]
}

const SOURCES = [
  { title: 'Seasonal Agricultural Survey 2024', text: 'Plot-level production, seeds, fertilizer, practices and irrigation for Seasons A, B and C.', tag: 'NISR · SAS' },
  { title: 'Seasonal Agricultural Survey 2025', text: 'Same modules for 2025, enabling year-on-year comparison by crop and district.', tag: 'NISR · SAS' },
  { title: 'Agriculture Household Survey 2024', text: 'Household access to extension, cooperatives, insurance and environmental awareness.', tag: 'NISR · AHS' },
  { title: 'Rwanda district boundaries', text: 'Administrative level 2 boundaries used for all district maps.', tag: 'geoBoundaries' },
]

export default function Methods() {
  const m = useApi<Methodology>('/metadata/methodology')
  const indicators = useApi<IndicatorDef[]>('/indicators')

  return (
    <>
      <PageHero crumb="Data & methods" title="Data & methodology"
        lead="How Analiza turns NISR microdata into reliable, survey-weighted indicators, and the limits you should keep in mind." />

      <section id="sources" className="section section--blue">
        <div className="container">
          <SectionHead title="Data sources" lead="All agricultural data comes from the NISR Microdata Portal. Raw microdata is not redistributed; only aggregated results are published." />
          <div className="grid grid-4">
            {SOURCES.map((s) => (
              <div key={s.title} className="survey-card">
                <span className="badge" style={{ alignSelf: 'flex-start' }}>{s.tag}</span>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
                <a className="more" href="https://microdata.statistics.gov.rw/index.php/catalog" target="_blank" rel="noreferrer">Microdata portal <Icon name="chevronRight" size={14} /></a>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="model" className="section">
        <div className="container grid grid-2">
          <div>
            <SectionHead title="Processing pipeline" />
            <ol className="steps">
              <li><div><strong>Load</strong><br /><span className="small muted">38 Stata files read with their value labels (Python, pyreadstat).</span></div></li>
              <li><div><strong>Harmonise</strong><br /><span className="small muted">2024 and 2025 questionnaires mapped to common variables; skip patterns resolved; district names standardised.</span></div></li>
              <li><div><strong>Clean</strong><br /><span className="small muted">Crop areas from the screening module, implausible areas capped, extreme yields (top 1% per crop) removed.</span></div></li>
              <li><div><strong>Weight and aggregate</strong><br /><span className="small muted">Survey weights applied; indicators computed at national, province and district level; small cells suppressed.</span></div></li>
              <li><div><strong>Model</strong><br /><span className="small muted">Gradient-boosted yield model trained to estimate adoption scenarios.</span></div></li>
              <li><div><strong>Serve</strong><br /><span className="small muted">FastAPI serves the aggregated tables to this React interface and as an open API.</span></div></li>
            </ol>
          </div>
          <div className="stack">
            <SectionHead title="Coverage & model" />
            {m.loading && <Loader />}
            {m.error && <ErrorBox message={m.error} />}
            {m.data && (
              <div className="card card-pad">
                <dl className="dl">
                  <dt>Plot-crop records</dt><dd><strong>{num(m.data.coverage.plot_crop_records)}</strong></dd>
                  <dt>Households (AHS)</dt><dd><strong>{num(m.data.coverage.households)}</strong></dd>
                  <dt>Seasons</dt><dd>{m.data.coverage.seasons.map((s) => `${s.year}${s.season}`).join(', ')}</dd>
                  <dt>Crops published</dt><dd>{m.data.crops.length}</dd>
                  <dt>Yield model</dt><dd>{m.data.model.model}</dd>
                  <dt>Holdout accuracy</dt><dd>R² = <strong>{m.data.model.r2_log_yield}</strong> on log yield ({num(m.data.model.test_rows)} test plots)</dd>
                  <dt>Model features</dt><dd className="small">{m.data.model.features.join(', ').replaceAll('_', ' ')}</dd>
                  <dt>Data processed</dt><dd>{new Date(m.data.generated_at).toLocaleString()}</dd>
                </dl>
              </div>
            )}
            {m.data && (
              <div className="card card-pad">
                <h3 style={{ fontSize: 16, marginBottom: 10 }}>Methodological notes</h3>
                <ul className="profile-list">
                  {m.data.notes.map((n) => <li key={n} style={{ justifyContent: 'flex-start' }}><Icon name="check" size={16} style={{ color: 'var(--blue)', flexShrink: 0 }} /> {n}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      </section>

      <section id="catalogue" className="section section--alt">
        <div className="container">
          <SectionHead title="Indicator catalogue" lead="Every indicator available in Analiza, its unit and definition." />
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>Indicator</th><th>Unit</th><th>Topic</th><th>Definition</th><th>Source</th></tr></thead>
              <tbody>
                {indicators.data?.map((i) => (
                  <tr key={i.id}>
                    <td><strong>{i.name}</strong></td><td style={{ whiteSpace: 'nowrap' }}>{i.unit}</td>
                    <td><span className="badge">{i.topic}</span></td><td className="small">{i.description}</td><td className="small muted">{i.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </>
  )
}
