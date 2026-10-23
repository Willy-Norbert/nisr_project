import type { Insight } from '../lib/api'
import { C, GroupedBars, RankingBars, ScatterPlot, SimpleBars } from './charts'

type Row = Record<string, number | string>

export default function InsightVisual({ insight, compact = false }: { insight: Insight; compact?: boolean }) {
  const ev = insight.evidence as Row[]
  const h = compact ? 220 : 280

  switch (insight.id) {
    case 'yield-trend':
      return (
        <GroupedBars height={h} unit="kg/ha" keys={['previous', 'current']} labels={['Previous year', 'Latest year']}
          colors={[C.grey, C.blue]} data={ev.map((r) => ({ name: String(r.crop), previous: r.previous, current: r.current }))} />
      )
    case 'seed-premium':
    case 'fertilizer-premium':
      return (
        <GroupedBars height={h} unit="kg/ha" keys={['with', 'without']}
          labels={[insight.id === 'seed-premium' ? 'Improved seed' : 'With fertilizer', insight.id === 'seed-premium' ? 'Local seed' : 'Without']}
          data={ev.slice(0, compact ? 4 : 6).map((r) => ({ name: String(r.crop), with: r.yield_with, without: r.yield_without }))} />
      )
    case 'district-spread': {
      const rows = ev.map((r) => ({ name: String(r.area), value: Number(r.value) }))
      const data = compact ? [...rows.slice(0, 4), ...rows.slice(-4)] : rows
      return <RankingBars data={data} unit="kg/ha" height={compact ? h : undefined} />
    }
    case 'model-potential':
      return (
        <SimpleBars height={h} unit="%" digits={1} color={C.gold}
          data={ev.slice(0, compact ? 6 : 10).map((r) => ({ name: String(r.district), value: Number(r.change_pct) }))} />
      )
    case 'gender-gap':
      return (
        <GroupedBars height={h} unit="kg/ha" keys={['Female', 'Male']} labels={['Female farmers', 'Male farmers']}
          colors={[C.gold, C.blue]} data={ev.slice(0, 1).map((r) => ({ name: 'Maize, Rwanda', Female: r.Female, Male: r.Male }))} />
      )
    case 'extension-link':
      return (
        <ScatterPlot height={h} xLabel="Households with extension access" yLabel="Plots with inorganic fertilizer"
          data={ev.map((r) => ({ name: String(r.district), x: Number(r.extension), y: Number(r.fertilizer) }))} />
      )
    case 'irrigation':
      return <SimpleBars height={h} unit="% of plots" digits={1} data={ev.map((r) => ({ name: `Season ${r.season}`, value: Number(r.value) }))} />
    default:
      return null
  }
}
