import { Icon } from '../components/Icons'
import { ErrorBox, Loader, PageHero, SectionHead } from '../components/ui'
import type { AskStatus, IndicatorDef } from '../lib/api'
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
  const ask = useApi<AskStatus>('/ask/status')
  const clf = ask.data?.classifier

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
        <div className="container">
          <div className="grid grid-2 methods-top-grid" style={{ alignItems: 'stretch', gap: 24 }}>
            <div className="methods-col">
              <SectionHead title="Processing pipeline" lead="Automated end-to-end data pipeline from raw microdata to publication." />
              <div className="card card-pad pipeline-card">
                <ol className="steps">
                  <li>
                    <div>
                      <strong>Load</strong>
                      <span className="small muted">38 Stata files read with their value labels (Python, pyreadstat).</span>
                    </div>
                  </li>
                  <li>
                    <div>
                      <strong>Harmonise</strong>
                      <span className="small muted">2024 and 2025 questionnaires mapped to common variables; skip patterns resolved; district names standardised.</span>
                    </div>
                  </li>
                  <li>
                    <div>
                      <strong>Clean</strong>
                      <span className="small muted">Crop areas from the screening module, implausible areas capped, extreme yields (top 1% per crop) removed.</span>
                    </div>
                  </li>
                  <li>
                    <div>
                      <strong>Weight and aggregate</strong>
                      <span className="small muted">Survey weights applied; indicators computed at national, province and district level; small cells suppressed.</span>
                    </div>
                  </li>
                  <li>
                    <div>
                      <strong>Model</strong>
                      <span className="small muted">Gradient-boosted yield model trained to estimate adoption scenarios.</span>
                    </div>
                  </li>
                  <li>
                    <div>
                      <strong>Serve</strong>
                      <span className="small muted">FastAPI serves the aggregated tables to this React interface and as an open API.</span>
                    </div>
                  </li>
                </ol>
              </div>
            </div>

            <div className="methods-col">
              <SectionHead title="Coverage & model" lead="Key statistical scope and machine-learning model specifications." />
              {m.loading && <Loader />}
              {m.error && <ErrorBox message={m.error} />}
              {m.data && (
                <div className="card card-pad coverage-card">
                  <dl className="coverage-dl">
                    <div className="coverage-row">
                      <dt>Plot-crop records</dt>
                      <dd><strong>{num(m.data.coverage.plot_crop_records)}</strong></dd>
                    </div>
                    <div className="coverage-row">
                      <dt>Households (AHS)</dt>
                      <dd><strong>{num(m.data.coverage.households)}</strong></dd>
                    </div>
                    <div className="coverage-row">
                      <dt>Seasons</dt>
                      <dd className="season-badges">
                        {m.data.coverage.seasons.map((s) => (
                          <span key={`${s.year}${s.season}`} className="season-pill">{s.year}{s.season}</span>
                        ))}
                      </dd>
                    </div>
                    <div className="coverage-row">
                      <dt>Crops published</dt>
                      <dd><strong>{m.data.crops.length}</strong> crops</dd>
                    </div>
                    <div className="coverage-row">
                      <dt>Yield model</dt>
                      <dd><code className="code-badge">{m.data.model.model}</code></dd>
                    </div>
                    <div className="coverage-row">
                      <dt>Holdout accuracy</dt>
                      <dd>
                        <span className="accuracy-badge">R² = {m.data.model.r2_log_yield}</span>
                        <span className="small muted" style={{ marginLeft: 6 }}>({num(m.data.model.test_rows)} test plots)</span>
                      </dd>
                    </div>
                    <div className="coverage-row coverage-row--features">
                      <dt>Model features</dt>
                      <dd className="feature-tag-list">
                        {m.data.model.features.map((f) => (
                          <span key={f} className="feature-tag">{f.replaceAll('_', ' ')}</span>
                        ))}
                      </dd>
                    </div>
                    <div className="coverage-row">
                      <dt>Data processed</dt>
                      <dd className="small muted">{new Date(m.data.generated_at).toLocaleString()}</dd>
                    </div>
                  </dl>
                </div>
              )}
            </div>
          </div>

          {m.data && (
            <div className="card card-pad method-notes-card">
              <div className="method-notes-head">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="badge" style={{ background: 'var(--blue-50)', color: 'var(--blue)', fontWeight: 700 }}>
                    NISR Standards
                  </span>
                  <h3 style={{ fontSize: 18, margin: 0 }}>Methodological notes</h3>
                </div>
                <p className="small muted" style={{ margin: 0 }}>
                  Official survey weighting protocols, calculation standards, and data reliability thresholds.
                </p>
              </div>

              <div className="method-notes-grid">
                {m.data.notes.map((n, i) => (
                  <div key={i} className="method-note-item">
                    <span className="method-note-icon">
                      <Icon name="check" size={15} />
                    </span>
                    <span className="method-note-text">{n}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      <section id="ask" className="section">
        <div className="container">
          <SectionHead title="How “Ask the data” works"
            lead="Analiza's own natural-language model. No external AI service: every number in an answer comes from the NISR tables." />
          <div className="method-notes-grid">
            {[
              ['1. Understand the words', 'An entity finder spots crops, districts, provinces, measures, inputs, year and season in English, Kinyarwanda or French. Typos are corrected by fuzzy matching (“mesanze” → Musanze, “ibigori” → maize) and the answer shows what was understood.'],
              ['2. Classify the question', `A scikit-learn classifier (${clf?.algorithm ?? 'TF-IDF n-grams + logistic regression'}) sorts the question into one of ${clf?.intents ?? 19} types, trained on ${clf?.training_examples ? num(clf.training_examples) : '2,000+'} example questions. Names are masked first, so it works for every crop and district.`],
              ['3. Query the survey tables', 'Each question type runs fixed, survey-weighted queries. What-if questions use the gradient-boosted yield model above.'],
              ['4. Answer with evidence', 'Answers are written from templates filled with the retrieved numbers, with maps and charts. Fair comparisons only: same crop and period, Season A vs Season A, and results on fewer than 30 observations flagged.'],
            ].map(([t, d]) => (
              <div key={t} className="method-note-item">
                <span className="method-note-icon"><Icon name="check" size={15} /></span>
                <span className="method-note-text"><strong>{t}.</strong> {d}</span>
              </div>
            ))}
          </div>
          {clf?.test_accuracy != null && (
            <p className="small muted" style={{ marginTop: 12 }}>
              Classifier accuracy: <strong>{Math.round((clf.test_accuracy ?? 0) * 100)}%</strong> on hand-written test
              questions it never saw. Questions outside the surveys (prices, weather, pests, other countries, years after
              2025) are declined with suggestions of what the data can answer.
            </p>
          )}
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
