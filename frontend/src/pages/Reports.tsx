import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Icon } from '../components/Icons'
import { ErrorBox, Field, Note, PageHero, Segmented, Select } from '../components/ui'
import { api } from '../lib/api'
import type { Filters, Season } from '../lib/api'
import { useApi } from '../lib/useApi'

type Scope = 'national' | 'district'
type Format = 'pdf' | 'csv'

export default function Reports() {
  const filters = useApi<Filters>('/metadata/filters')
  const [scope, setScope] = useState<Scope>('district')
  const [params] = useSearchParams()
  const [district, setDistrict] = useState(params.get('district') ?? 'Huye')
  const [crop, setCrop] = useState('Maize')
  const [year, setYear] = useState(2025)
  const [season, setSeason] = useState<Season>('A')
  const [format, setFormat] = useState<Format>('pdf')
  const [busy, setBusy] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  // Preview modal state
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewFilename, setPreviewFilename] = useState<string | null>(null)

  const generate = async () => {
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      const res = await api.post<{ download_url: string; filename: string }>('/reports', {
        year, season, crop, district: scope === 'district' ? district : null, format,
      })
      const a = document.createElement('a')
      a.href = (import.meta.env.VITE_API_URL ?? '') + res.download_url
      a.download = res.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      setDone(res.filename)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const handlePreview = async () => {
    setPreviewLoading(true)
    setError(null)
    try {
      const res = await api.post<{ download_url: string; preview_url?: string; filename: string }>('/reports', {
        year, season, crop, district: scope === 'district' ? district : null, format: 'pdf',
      })
      const baseUrl = import.meta.env.VITE_API_URL ?? ''
      const url = baseUrl + (res.preview_url || res.download_url)
      setPreviewUrl(url)
      setPreviewFilename(res.filename)
      setPreviewOpen(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPreviewLoading(false)
    }
  }

  const crops = (filters.data?.crops ?? ['Maize']).filter((c) => c !== 'All crops')

  return (
    <>
      <PageHero crumb="Reports" title="Reports & downloads"
        lead="Generate an evidence summary for a planning meeting: key indicators, crop yields, priority districts and findings, ready to share." />
      <section className="section section--alt">
        <div className="container grid" style={{ gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 1fr)' }}>
          <div className="card">
            <div className="card-head"><h3>Build your report</h3></div>
            <div className="card-body stack" style={{ gap: 18 }}>
              <Field label="Coverage">
                <Segmented value={scope} onChange={setScope} options={[{ value: 'district', label: 'One district' }, { value: 'national', label: 'Rwanda (national)' }]} />
              </Field>
              <div className="row" style={{ alignItems: 'flex-end' }}>
                {scope === 'district' && filters.data && (
                  <Field label="District"><Select value={district} onChange={setDistrict} options={filters.data.districts} /></Field>
                )}
                <Field label="Focus crop"><Select value={crop} onChange={setCrop} options={crops} /></Field>
              </div>
              {filters.data && (
                <div className="row">
                  <Field label="Year"><Select value={year} onChange={setYear} options={filters.data.years} /></Field>
                  <Field label="Season"><Select value={season} onChange={setSeason} options={['A', 'B'] as Season[]} format={(s) => `Season ${s}`} /></Field>
                </div>
              )}
              <Field label="Format">
                <Segmented value={format} onChange={setFormat} options={[{ value: 'pdf', label: 'PDF report' }, { value: 'csv', label: 'CSV (priority table)' }]} />
              </Field>
              <div className="row" style={{ gap: 12, alignItems: 'center' }}>
                <button className="btn btn-primary" onClick={generate} disabled={busy || previewLoading}>
                  <Icon name="download" size={16} /> {busy ? 'Generating…' : 'Generate & download'}
                </button>
                <button className="btn btn-outline" onClick={handlePreview} disabled={busy || previewLoading} type="button">
                  <Icon name="file" size={16} /> {previewLoading ? 'Preparing preview…' : 'Preview report'}
                </button>
                {done && <span className="small" style={{ color: 'var(--green)' }}><Icon name="check" size={14} /> {done} downloaded</span>}
              </div>
              {error && <ErrorBox message={error} />}
            </div>
          </div>

          <div className="stack">
            <div className="card card-pad">
              <h3 style={{ fontSize: 16, marginBottom: 12 }}>What's in the PDF report</h3>
              <ol className="steps">
                <li><div><strong>Institutional NISR &amp; Analiza header</strong><br /><span className="small muted">Official National Institute of Statistics of Rwanda (NISR) emblem on the left, FarmGap Rwanda branding on the right.</span></div></li>
                <li><div><strong>Geographic district map</strong><br /><span className="small muted">Dynamic map of Rwanda highlighting the selected district with administrative metrics and priority rank.</span></div></li>
                <li><div><strong>Latest survey findings &amp; actions</strong><br /><span className="small muted">Data-driven findings on yield gaps, input adoption bottlenecks, top local crops, and recommended interventions.</span></div></li>
                <li><div><strong>SAS indicators &amp; crop yields</strong><br /><span className="small muted">Full table of 13 agricultural indicators and crop productivity (kg/ha) benchmarked against the national average.</span></div></li>
              </ol>
            </div>
            <Note>Reports are generated on demand from the latest processed data. No account is needed. Official data:
              National Institute of Statistics of Rwanda (NISR), Seasonal Agricultural Survey 2024–2025 &amp; Agriculture Household Survey 2024.</Note>
          </div>
        </div>
      </section>

      {/* PDF Preview Popup Modal */}
      {previewOpen && previewUrl && (
        <div className="modal-overlay" onClick={() => setPreviewOpen(false)} role="dialog" aria-modal="true">
          <div className="pdf-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <Icon name="file" size={20} />
                <div>
                  <strong className="modal-filename">{previewFilename}</strong>
                  <span className="modal-meta">Official NISR Data Evidence Report</span>
                </div>
              </div>
              <div className="modal-actions">
                <a
                  href={previewUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-sm btn-outline"
                  title="Open in a new tab"
                >
                  <Icon name="arrowUpRight" size={14} />
                  <span>Open in tab</span>
                </a>
                <a
                  href={previewUrl}
                  download={previewFilename || 'report.pdf'}
                  className="btn btn-sm btn-primary"
                >
                  <Icon name="download" size={14} />
                  <span>Download</span>
                </a>
                <button
                  className="modal-close-btn"
                  onClick={() => setPreviewOpen(false)}
                  aria-label="Close preview"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="pdf-modal-body">
              <iframe
                src={`${previewUrl}#toolbar=1&navpanes=0&view=FitH`}
                className="pdf-iframe"
                title="PDF Report Preview"
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
