import { useEffect, useState } from 'react'
import { SimpleBars } from '../components/charts'
import { Icon } from '../components/Icons'
import type { IconName } from '../components/Icons'
import { ErrorBox, Field, Loader, Note, PageHero, Select } from '../components/ui'
import { qs } from '../lib/api'
import type { ScenarioOptions, ScenarioResult, Season } from '../lib/api'
import { INPUT_LABELS, compact, num, signed } from '../lib/format'
import { useApi } from '../lib/useApi'

const INPUT_ICONS: Record<string, IconName> = { improved_seed: 'seed', inorganic_fertilizer: 'flask', organic_fertilizer: 'sprout', irrigated: 'drop' }
const INPUT_HELP: Record<string, string> = {
  improved_seed: 'Certified / hybrid seed',
  inorganic_fertilizer: 'DAP, NPK, urea',
  organic_fertilizer: 'Manure or compost',
  irrigated: 'Any irrigation on the plot',
}

export default function Simulator() {
  const options = useApi<ScenarioOptions>('/scenarios/options')
  const [crop, setCrop] = useState('Maize')
  const [district, setDistrict] = useState('Nyagatare')
  const [season, setSeason] = useState<Season>('A')
  const [inputs, setInputs] = useState<string[]>(['improved_seed', 'inorganic_fertilizer'])

  const result = useApi<ScenarioResult>(`/scenarios${qs({ crop, district, season, inputs })}`)
  const [last, setLast] = useState<ScenarioResult | null>(null)
  useEffect(() => {
    if (result.data) setLast(result.data)
  }, [result.data])

  const toggle = (id: string) => setInputs((xs) => (xs.includes(id) ? xs.filter((x) => x !== id) : [...xs, id]))
  const r = result.data ?? last
  const model = options.data?.model

  return (
    <>
      <PageHero crumb="Simulator" title="Yield scenario simulator"
        lead="Estimate how average yields in a district could change if every surveyed plot adopted a package of inputs. Powered by a machine-learning model trained on NISR plot data." />
      <section className="section section--alt" style={{ paddingTop: 28 }}>
        <div className="container">
          {options.error && <ErrorBox message={options.error} />}
          <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 0.9fr) minmax(0, 1.4fr)' }}>
            <div className="card">
              <div className="card-head"><h3>1. Choose a crop and place</h3></div>
              <div className="card-body stack" style={{ gap: 14 }}>
                {options.data ? (
                  <>
                    <Field label="Crop"><Select value={crop} onChange={setCrop} options={options.data.crops} /></Field>
                    <Field label="District"><Select value={district} onChange={setDistrict} options={options.data.districts} /></Field>
                    <Field label={`Season (${options.data.year})`}><Select value={season} onChange={setSeason} options={options.data.seasons} format={(s) => `Season ${s}`} /></Field>
                  </>
                ) : <Loader />}
              </div>
              <div className="card-head" style={{ borderTop: '1px solid var(--border)' }}><h3>2. Select inputs to adopt</h3></div>
              <div className="card-body stack" style={{ gap: 10 }}>
                {Object.keys(INPUT_LABELS).map((id) => (
                  <button key={id} className={`toggle${inputs.includes(id) ? ' on' : ''}`} onClick={() => toggle(id)} aria-pressed={inputs.includes(id)}>
                    <span className="toggle-label">
                      <span className="kpi-icon" style={{ width: 36, height: 36, margin: 0 }}><Icon name={INPUT_ICONS[id]} size={18} /></span>
                      <span>{INPUT_LABELS[id]}<small>{INPUT_HELP[id]}{r ? ` · now ${num(r.current_adoption_pct[id], 0)}% of plots` : ''}</small></span>
                    </span>
                    <span className="switch" />
                  </button>
                ))}
              </div>
            </div>

            <div className="stack">
              <div className="card card-pad">
                <h3 style={{ fontSize: 16, marginBottom: 14 }}>3. Estimated result · {crop} in {district}</h3>
                {result.error && <ErrorBox message={result.error} />}
                {r && !result.error && (
                  <>
                    <div className="result-hero" style={{ opacity: result.loading ? 0.6 : 1 }}>
                      <div><small>Current estimate</small><strong>{num(r.current_yield)}</strong><span className="unit">kg/ha</span></div>
                      <div className="result-arrow"><Icon name="arrowRight" /></div>
                      <div>
                        <small>{r.inputs.length ? 'With selected inputs' : 'Select inputs'}</small>
                        <strong>{num(r.scenario_yield)}</strong><span className="unit">kg/ha</span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <span className="result-change">{signed(r.change_pct)} estimated change in average yield</span>
                    </div>
                    <p className="small muted" style={{ textAlign: 'center', marginBottom: 0 }}>
                      Based on {num(r.n_plots)} surveyed {crop.toLowerCase()} plots in {district}, {r.year} Season {r.season}.
                    </p>
                  </>
                )}
                {!r && <Loader />}
              </div>

              <div className="card">
                <div className="card-head"><h3>Effect of each input on its own</h3><small>% change in average yield</small></div>
                <div className="card-body">
                  {r ? (
                    <SimpleBars unit="%" digits={1}
                      data={r.single_input_effects.map((e) => ({ name: INPUT_LABELS[e.input], value: e.change_pct }))} />
                  ) : <Loader />}
                </div>
              </div>

              <Note>
                {r?.note}{' '}
                {model && <>Model: gradient-boosted trees on log(yield), trained on {compact(model.train_rows + model.test_rows)} plots; holdout R² = {model.r2_log_yield}.</>}
              </Note>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
