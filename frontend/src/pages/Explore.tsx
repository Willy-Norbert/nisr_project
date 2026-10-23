import { Fragment, useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent, ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import DistrictFocusMap from '../components/DistrictFocusMap'
import { GroupedBars, RankingBars, SimpleBars, TrendChart, C } from '../components/charts'
import { Icon } from '../components/Icons'
import type { IconName } from '../components/Icons'
import { api } from '../lib/api'
import type { AskResponse, AskStatus, DistrictComparison, DistrictProfile, InputEffect, Overview, Priorities, ScenarioResult, SeasonSeries } from '../lib/api'
import { INPUT_LABELS, num, signed, valueWithUnit } from '../lib/format'
import { useApi } from '../lib/useApi'

type Message = { role: 'user'; text: string } | { role: 'bot'; res: AskResponse } | { role: 'error'; text: string }

const TOPICS: { label: string; icon: IconName; q: string }[] = [
  { label: 'Crop yields by district', icon: 'map', q: 'Which districts have the highest maize yield?' },
  { label: 'Seasonal trends', icon: 'chart', q: 'How has Irish potato yield changed across seasons?' },
  { label: 'Impact of improved seed', icon: 'seed', q: 'Does improved seed increase maize yield?' },
  { label: 'Fertilizer use', icon: 'flask', q: 'Which districts have the lowest fertilizer use?' },
  { label: 'Women farmers', icon: 'users', q: 'Compare women and men farmers maize yields' },
  { label: 'What-if scenarios', icon: 'sliders', q: 'What if farmers in Nyagatare used improved seed and fertilizer for maize?' },
  { label: 'Priority districts', icon: 'target', q: 'Where should support be prioritised for beans?' },
  { label: 'District profile', icon: 'home', q: 'Tell me about Musanze district' },
]

const EXAMPLES = [
  'Which districts have the highest maize yield?',
  'How has Irish potato yield changed across seasons?',
  'What if farmers in Nyagatare used improved seed and fertilizer?',
]

const CAPABILITIES = [
  'Answers in plain language in English, Kinyarwanda or French',
  'Generates interactive crop yield charts, seasonal trends & district maps',
  'Trained on NISR SAS 2024–2025 & Agriculture Household Survey microdata',
]

const LIMITATIONS = [
  'May occasionally require clarification on specific administrative cells',
  'Simulation scenarios show statistical associations, not guaranteed effects',
  'Evidence strictly bounded by official NISR surveys up to 2025',
]

const INTENT_LABEL: Record<string, string> = {
  districts: 'District ranking', trend: 'Trend over seasons', inputs: 'Input effect', gender: 'Gender comparison',
  scenario: 'Model scenario', priorities: 'Priority ranking', profile: 'District profile', chat: 'Conversation',
  overview: 'National overview',
}

export default function Explore() {
  const [params, setParams] = useSearchParams()
  const status = useApi<AskStatus>('/ask/status')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [sideOpen, setSideOpen] = useState(false)
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('farmgap_chat_theme')
    return saved !== null ? saved === 'dark' : true
  })
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const asked = useRef<string | null>(null)

  useEffect(() => {
    localStorage.setItem('farmgap_chat_theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  const ask = async (question: string) => {
    if (!question.trim() || busy) return
    const history = messages.flatMap((m) =>
      m.role === 'user' ? [{ role: 'user', content: m.text }] : m.role === 'bot' ? [{ role: 'assistant', content: m.res.answer }] : [])
    setMessages((m) => [...m, { role: 'user', text: question }])
    setInput('')
    setSideOpen(false)
    setBusy(true)
    try {
      const res = await api.post<AskResponse>('/ask', { question, history })
      setMessages((m) => [...m, { role: 'bot', res }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'error', text: (e as Error).message }])
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }

  useEffect(() => {
    const q = params.get('q')
    if (q && asked.current !== q) {
      asked.current = q
      ask(q)
      setParams({}, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, busy])

  useEffect(() => {
    const el = inputRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`
      el.style.overflowY = el.scrollHeight > 160 ? 'auto' : 'hidden'
    }
  }, [input])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    ask(input)
  }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      ask(input)
    }
  }

  const aiOn = status.data?.ai_enabled

  return (
    <div className={`chat-app ${darkMode ? 'dark-theme' : 'light-theme'}`}>
      <aside className={`chat-side${sideOpen ? ' open' : ''}`}>
        <div className="chat-side-top">
          <button className="chat-new-btn" onClick={() => setMessages([])}>
            <Icon name="plus" size={16} />
            <span>New chat</span>
          </button>
        </div>

        <div className="chat-side-group">
          <span className="chat-side-heading">Explore by topic</span>
          <div className="chat-topic-list">
            {TOPICS.map((t) => (
              <button key={t.label} className="chat-topic-item" onClick={() => ask(t.q)} disabled={busy}>
                <Icon name={t.icon} size={16} />
                <span className="chat-topic-label">{t.label}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="chat-side-bottom">
          <a
            href="https://microdata.statistics.gov.rw"
            target="_blank"
            rel="noreferrer"
            className="chat-side-nav-item"
            title="NISR Microdata catalog"
          >
            <Icon name="database" size={16} />
            <span>NISR Microdata</span>
          </a>
          <button
            className="chat-side-nav-item"
            onClick={() => setDarkMode((d) => !d)}
            title="Toggle theme"
            type="button"
          >
            <Icon name={darkMode ? 'sun' : 'moon'} size={16} />
            <span>{darkMode ? 'Light mode' : 'Dark mode'}</span>
          </button>
          <Link to="/" className="chat-side-nav-item" title="Exit to home">
            <Icon name="logOut" size={16} />
            <span>Back to FarmGap</span>
          </Link>
        </div>
      </aside>

      <div className="chat-main">
        <header className="chat-top">
          <button className="chat-icon-btn chat-menu" onClick={() => setSideOpen((o) => !o)} aria-label="Toggle menu">
            <Icon name="layers" size={18} />
          </button>
          <div className="chat-top-brand">
            <img src="/logo.png" alt="" className="chat-top-logo" />
            <span className="chat-top-title">FarmGap AI</span>
          </div>
          <div className="spacer" />
          <span className={`chat-status${aiOn ? ' on' : ''}`}>
            <span className="dot" /> {status.loading ? 'Connecting…' : aiOn ? `AI · ${status.data?.model}` : 'Data Assistant (NISR)'}
          </span>
          <Link to="/" className="chat-icon-btn chat-desktop-back" title="Back to FarmGap">
            <Icon name="home" size={16} />
          </Link>
        </header>

        <div className="chat-scroll">
          <div className="chat-thread">
            {messages.length === 0 && (
              <div className="chat-landing">
                <div className="chat-landing-hero">
                  <div className="chat-landing-badge">
                    <img src="/logo.png" alt="FarmGap logo" />
                  </div>
                  <h1>FarmGap AI</h1>
                  <p>Ask in plain language. Grounded in NISR agricultural surveys, with real-time charts and maps.</p>
                </div>

                <div className="chat-columns">
                  {/* Column 1: Examples */}
                  <div className="chat-col">
                    <div className="chat-col-head">
                      <Icon name="sun" size={24} />
                      <h2>Examples</h2>
                    </div>
                    <div className="chat-col-cards">
                      {EXAMPLES.map((ex) => (
                        <button key={ex} className="chat-card chat-card--clickable" onClick={() => ask(ex)}>
                          <span>"{ex}"</span>
                          <span className="chat-card-arrow">&rarr;</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Column 2: Capabilities */}
                  <div className="chat-col">
                    <div className="chat-col-head">
                      <Icon name="zap" size={24} />
                      <h2>Capabilities</h2>
                    </div>
                    <div className="chat-col-cards">
                      {CAPABILITIES.map((cap) => (
                        <div key={cap} className="chat-card">
                          <span>{cap}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Column 3: Limitations */}
                  <div className="chat-col">
                    <div className="chat-col-head">
                      <Icon name="alert" size={24} />
                      <h2>Limitations</h2>
                    </div>
                    <div className="chat-col-cards">
                      {LIMITATIONS.map((lim) => (
                        <div key={lim} className="chat-card">
                          <span>{lim}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {messages.map((m, i) =>
              m.role === 'user' ? (
                <div key={i} className="msg-user">{m.text}</div>
              ) : m.role === 'error' ? (
                <div key={i} className="error">Something went wrong: {m.text}</div>
              ) : (
                <BotMessage key={i} res={m.res} onAsk={ask} />
              ),
            )}

            {busy && (
              <div className="msg-bot">
                <span className="msg-avatar"><img src="/logo.png" alt="" /></span>
                <div className="msg-answer">
                  <span className="typing"><span /><span /><span /></span>
                  <span className="muted small">Analysing NISR survey data…</span>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <div className="chat-composer-wrap">
          <form className="chat-composer" onSubmit={submit}>
            <div className="chat-input-bar">
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                autoFocus
                placeholder="Ask about yields, inputs, a district or a what-if scenario…"
                aria-label="Your question"
              />
              <button
                className="chat-send-btn"
                disabled={busy || !input.trim()}
                type="submit"
                aria-label="Send"
              >
                <Icon name="send" size={16} />
              </button>
            </div>
            <p className="chat-disclaimer">
              FarmGap AI Version 2026. Free Research Preview. Grounded in NISR SAS 2024–2025 &amp; Household Survey microdata.
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}

/** Renders the small markdown subset the assistant uses: "- " bullets, **bold** and paragraphs. */
function RichText({ text }: { text: string }) {
  const inline = (s: string): ReactNode[] => s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>)
  const blocks: ReactNode[] = []
  let list: string[] = []
  const flush = () => {
    if (list.length) blocks.push(<ul key={blocks.length}>{list.map((l, i) => <li key={i}>{inline(l)}</li>)}</ul>)
    list = []
  }
  for (const line of text.split('\n')) {
    const t = line.trim()
    if (/^[-*•]\s+/.test(t)) list.push(t.replace(/^[-*•]\s+/, ''))
    else {
      flush()
      if (t) blocks.push(<p key={blocks.length}>{inline(t)}</p>)
    }
  }
  flush()
  return <div className="rich">{blocks}</div>
}

function BotMessage({ res, onAsk }: { res: AskResponse; onAsk: (q: string) => void }) {
  const p = res.parsed
  const followUps = p.district
    ? [`How has maize yield changed in ${p.district}?`, `What if farmers in ${p.district} used improved seed and fertilizer?`]
    : p.crop ? [`Where should support be prioritised for ${p.crop.toLowerCase()}?`, `Does fertilizer increase ${p.crop.toLowerCase()} yield?`] : []
  return (
    <div className="msg-bot">
      <span className="msg-avatar"><img src="/logo.png" alt="" /></span>
      <div className="msg-body">
        <div className="msg-answer">
          <RichText text={res.answer} />
          {p.intent !== 'chat' && (
            <div className="msg-meta">
              <span className="badge">{INTENT_LABEL[p.intent] ?? p.intent}</span>
              {p.crop && <span className="badge badge--muted">{p.crop}</span>}
              {p.district && <span className="badge badge--muted">{p.district}</span>}
              <span className="badge badge--muted">{p.year} Season {p.season}</span>
              {res.ai && <span className="badge badge--muted"><Icon name="sparkle" size={11} /> AI-written</span>}
            </div>
          )}
        </div>
        {p.district && (
          <div className="msg-visual card">
            <div className="card-head"><h3>{p.district} District</h3>
              <Link className="view-all" to={`/districts/${encodeURIComponent(p.district)}`}>Open district page <Icon name="chevronRight" size={14} /></Link></div>
            <DistrictFocusMap district={p.district} height={280} />
          </div>
        )}
        {res.data != null && <div className="msg-visual card card-pad"><Visual res={res} /></div>}
        {followUps.length > 0 && (
          <div className="chips">{followUps.map((q) => <button key={q} className="chip" onClick={() => onAsk(q)}>{q}</button>)}</div>
        )}
      </div>
    </div>
  )
}

function Visual({ res }: { res: AskResponse }) {
  const { intent } = res.parsed
  if (intent === 'overview') {
    const d = res.data as Overview
    return (
      <>
        <div className="grid grid-4" style={{ gap: 12, marginBottom: 16 }}>
          {d.kpis.map((k) => (
            <div key={k.indicator_id} className="kpi kpi--left" style={{ boxShadow: 'none', border: '1px solid var(--border)' }}>
              <div className="kpi-label">{k.name}</div>
              <div className="kpi-value">{valueWithUnit(k.value, k.unit)}</div>
              <div className="kpi-meta">{k.period}</div>
            </div>
          ))}
        </div>
        <h4 style={{ fontSize: 14, marginBottom: 4 }}>Main crop yields, {d.year} Season {d.season} (kg/ha)</h4>
        <SimpleBars unit="kg/ha" data={d.crops.map((c) => ({ name: c.crop, value: c.yield_kg_ha }))} />
        <Link className="view-all" to="/dashboard">Explore every district <Icon name="chevronRight" size={14} /></Link>
      </>
    )
  }
  if (intent === 'districts') {
    const d = res.data as DistrictComparison
    const rows = d.districts.map((r) => ({ name: r.area, value: r.value }))
    return (
      <>
        <RankingBars data={rows} national={d.national_value} unit={d.indicator.unit} />
        <Link className="view-all" to={`/dashboard?indicator=${d.indicator.id}&crop=${encodeURIComponent(d.crop)}`}>Open on the map <Icon name="chevronRight" size={14} /></Link>
      </>
    )
  }
  if (intent === 'trend') {
    const d = res.data as SeasonSeries
    return d.series.length ? <TrendChart data={d.series} unit={d.indicator.unit} /> : <p className="empty">No data.</p>
  }
  if (intent === 'inputs') {
    const d = res.data as { effects: InputEffect[]; note: string }
    return (
      <>
        <GroupedBars unit="kg/ha" keys={['with', 'without']} labels={['With input', 'Without input']}
          data={d.effects.map((e) => ({ name: e.input_label, with: e.yield_with, without: e.yield_without }))} />
        <p className="small muted">{d.note}</p>
      </>
    )
  }
  if (intent === 'gender') {
    const d = res.data as { rows: Record<string, number | string>[] }
    return d.rows.length ? (
      <GroupedBars unit="kg/ha" keys={['Female', 'Male']} labels={['Female farmers', 'Male farmers']} colors={[C.gold, C.blue]}
        data={d.rows.map((r) => ({ name: String(r.area), Female: r.Female, Male: r.Male }))} />
    ) : <p className="empty">Not enough data.</p>
  }
  if (intent === 'scenario') {
    const d = res.data as ScenarioResult
    return (
      <>
        <div className="result-hero">
          <div><small>Current estimate</small><strong>{num(d.current_yield)}</strong><span className="unit">kg/ha</span></div>
          <div className="result-arrow"><Icon name="arrowRight" /></div>
          <div><small>With {d.inputs.map((i) => INPUT_LABELS[i].toLowerCase()).join(' + ')}</small><strong>{num(d.scenario_yield)}</strong><span className="unit">kg/ha</span></div>
        </div>
        <div style={{ textAlign: 'center' }}><span className="result-change">{signed(d.change_pct)} estimated yield</span></div>
        <Link className="view-all" style={{ marginTop: 12 }} to="/simulator">Try other combinations <Icon name="chevronRight" size={14} /></Link>
      </>
    )
  }
  if (intent === 'priorities') {
    const d = res.data as Priorities
    return (
      <>
        <SimpleBars unit="score" digits={1} data={d.districts.slice(0, 8).map((r) => ({ name: r.district, value: r.score }))} />
        <Link className="view-all" to="/priorities">See full method and ranking <Icon name="chevronRight" size={14} /></Link>
      </>
    )
  }
  if (intent === 'profile') {
    const d = res.data as DistrictProfile
    return (
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Crop</th><th className="num">{d.district} (kg/ha)</th><th className="num">Rwanda</th><th className="num">Difference</th></tr></thead>
          <tbody>
            {d.crop_yields.map((c) => (
              <tr key={c.crop}><td>{c.crop}</td><td className="num">{num(c.value)}</td><td className="num">{num(c.national_value)}</td>
                <td className="num" style={{ color: c.vs_national_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>{signed(c.vs_national_pct)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  return null
}
