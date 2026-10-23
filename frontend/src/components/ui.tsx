import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Banner } from './Banner'
import { Icon } from './Icons'
import type { IconName } from './Icons'
import { signed } from '../lib/format'

export function PageHero({
  title,
  lead,
}: {
  title: string
  lead?: string
  crumb?: string
}) {
  return (
    <Banner compact>
      <div className="page-hero">
        <h1>{title}</h1>
        {lead && <p>{lead}</p>}
      </div>
    </Banner>
  )
}

export function SectionHead({ title, lead, action }: { title: string; lead?: string; action?: ReactNode }) {
  return (
    <div className="section-head">
      <div>
        <h2>{title}</h2>
        {lead && <p>{lead}</p>}
      </div>
      {action}
    </div>
  )
}

export function ViewAll({ to, label = 'View all' }: { to: string; label?: string }) {
  return (
    <Link className="view-all" to={to}>
      {label} <Icon name="chevronRight" size={14} />
    </Link>
  )
}

export function Kpi({ icon, label, value, meta }: { icon: IconName; label: string; value: string; meta?: ReactNode }) {
  return (
    <div className="kpi">
      <div className="kpi-icon"><Icon name={icon} size={26} /></div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {meta && <div className="kpi-meta">{meta}</div>}
    </div>
  )
}

export function Delta({ value, suffix = '%', digits = 1, invert = false }: { value: number | null | undefined; suffix?: string; digits?: number; invert?: boolean }) {
  if (value === null || value === undefined) return <span className="muted small">–</span>
  const good = invert ? value < 0 : value > 0
  return (
    <span className={`delta ${good ? 'up' : value === 0 ? '' : 'down'}`}>
      <Icon name={value >= 0 ? 'trendUp' : 'trendDown'} size={14} />
      {signed(value, digits, suffix)}
    </span>
  )
}

export function Loader({ label = 'Loading data…' }: { label?: string }) {
  return <div className="loader"><div className="spinner" /> {label}</div>
}

export function ErrorBox({ message }: { message: string }) {
  return <div className="error">Could not load data: {message}. Is the API running on port 8000?</div>
}

export function Note({ children }: { children: ReactNode }) {
  return <div className="note"><Icon name="info" size={16} /><div>{children}</div></div>
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="field"><label>{label}</label>{children}</div>
}

export function Select<T extends string | number>({ value, onChange, options, format }: {
  value: T
  onChange: (v: T) => void
  options: readonly T[]
  format?: (v: T) => string
}) {
  return (
    <select className="select" value={value}
      onChange={(e) => onChange((typeof value === 'number' ? Number(e.target.value) : e.target.value) as T)}>
      {options.map((o) => <option key={o} value={o}>{format ? format(o) : o}</option>)}
    </select>
  )
}

export function Segmented<T extends string>({ value, onChange, options }: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
}) {
  return (
    <div className="segmented">
      {options.map((o) => (
        <button key={o.value} className={o.value === value ? 'active' : ''} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  )
}

export function ReliabilityBadge({ low }: { low: boolean | null | undefined }) {
  return low ? <span className="badge badge--gold" title="Fewer than 30 survey observations">Low sample</span> : null
}
