import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import InsightVisual from '../components/InsightVisual'
import { Icon } from '../components/Icons'
import { ErrorBox, Loader, Note, PageHero } from '../components/ui'
import type { Insight } from '../lib/api'
import { useApi } from '../lib/useApi'

export default function Insights() {
  const { hash } = useLocation()
  const { data, error, loading } = useApi<Insight[]>('/insights')

  useEffect(() => {
    if (data && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [data, hash])

  return (
    <>
      <PageHero crumb="Insights" title="Key insights"
        lead="Findings generated automatically from the processed survey tables. Each comes with its evidence and a suggested policy action." />
      <section className="section section--alt">
        <div className="container stack">
          <Note>Comparisons between plots that use an input and plots that don't are associations: farmers who adopt inputs
            may differ in other ways. Use them to prioritise, then validate in the field.</Note>
          {loading && <Loader />}
          {error && <ErrorBox message={error} />}
          <div className="grid grid-2">
            {data?.map((i) => (
              <article key={i.id} id={i.id} className="card insight" style={{ scrollMarginTop: 100 }}>
                <div className="insight-top">
                  <span className="badge">{i.topic}</span>
                  <span className="small muted"><Icon name="calendar" size={12} /> {i.period}</span>
                </div>
                <h3>{i.title}</h3>
                <p className="insight-summary">{i.summary}</p>
                <div className="insight-chart"><InsightVisual insight={i} /></div>
                <div className="insight-action"><Icon name="target" size={16} /><div><strong>Suggested action: </strong>{i.action}</div></div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}
