import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { num } from '../lib/format'

export const C = { blue: '#005baa', blueLight: '#7fb0de', gold: '#f5b800', grey: '#b8c4d0', green: '#18875a', red: '#c4372d' }
const axis = { fontSize: 12, fill: '#5d6d7e' }
const tooltipStyle = { borderRadius: 6, border: '1px solid #dbe2ea', fontSize: 13 }

export function RankingBars({ data, national, unit, highlight, height }: {
  data: { name: string; value: number }[]
  national?: number | null
  unit: string
  highlight?: string | null
  height?: number
}) {
  const digits = unit.startsWith('%') ? 1 : 0
  return (
    <ResponsiveContainer width="100%" height={height ?? Math.max(260, data.length * 22 + 40)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 48, top: 8, bottom: 8 }}>
        <CartesianGrid horizontal={false} stroke="#edf1f5" />
        <XAxis type="number" tick={axis} tickFormatter={(v) => num(v)} />
        <YAxis type="category" dataKey="name" width={96} tick={axis} interval={0} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${num(Number(v), digits)} ${unit}`, 'Value']} />
        {national != null && (
          <ReferenceLine x={national} stroke={C.gold} strokeWidth={2} strokeDasharray="4 3"
            label={{ value: 'Rwanda', position: 'top', fontSize: 11, fill: '#8a6400' }} />
        )}
        <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14}>
          {data.map((d) => <Cell key={d.name} fill={d.name === highlight ? C.gold : C.blue} />)}
          <LabelList dataKey="value" position="right" formatter={(v) => num(Number(v), digits)} style={{ fontSize: 11, fill: '#5d6d7e' }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function TrendChart({ data, unit, height = 260 }: { data: { period: string; value: number }[]; unit: string; height?: number }) {
  const digits = unit.startsWith('%') ? 1 : 0
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: 0, right: 20, top: 16, bottom: 4 }}>
        <CartesianGrid stroke="#edf1f5" vertical={false} />
        <XAxis dataKey="period" tick={axis} />
        <YAxis tick={axis} tickFormatter={(v) => num(v)} width={56} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${num(Number(v), digits)} ${unit}`, 'Value']} />
        <Line type="monotone" dataKey="value" stroke={C.blue} strokeWidth={3} dot={{ r: 5, fill: '#fff', strokeWidth: 3 }} activeDot={{ r: 7 }}>
          <LabelList dataKey="value" position="top" formatter={(v) => num(Number(v), digits)} style={{ fontSize: 11, fill: '#003c73' }} />
        </Line>
      </LineChart>
    </ResponsiveContainer>
  )
}

export function GroupedBars({ data, keys, labels, colors = [C.blue, C.grey], unit, height = 280 }: {
  data: Record<string, string | number>[]
  keys: string[]
  labels: string[]
  colors?: string[]
  unit: string
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ left: 0, right: 10, top: 20, bottom: 4 }}>
        <CartesianGrid stroke="#edf1f5" vertical={false} />
        <XAxis dataKey="name" tick={axis} interval={0} />
        <YAxis tick={axis} tickFormatter={(v) => num(v)} width={56} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [`${num(Number(v))} ${unit}`, String(n)]} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {keys.map((k, i) => (
          <Bar key={k} dataKey={k} name={labels[i]} fill={colors[i]} radius={[3, 3, 0, 0]} maxBarSize={38}>
            <LabelList dataKey={k} position="top" formatter={(v) => num(Number(v))} style={{ fontSize: 10.5, fill: '#5d6d7e' }} />
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

export function SimpleBars({ data, unit, color = C.blue, height = 260, digits = 0 }: {
  data: { name: string; value: number }[]
  unit: string
  color?: string
  height?: number
  digits?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ left: 0, right: 10, top: 22, bottom: 4 }}>
        <CartesianGrid stroke="#edf1f5" vertical={false} />
        <XAxis dataKey="name" tick={axis} interval={0} />
        <YAxis tick={axis} tickFormatter={(v) => num(v)} width={52} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${num(Number(v), digits)} ${unit}`, 'Value']} />
        <Bar dataKey="value" radius={[3, 3, 0, 0]} maxBarSize={46}>
          {data.map((d) => <Cell key={d.name} fill={d.value < 0 ? C.red : color} />)}
          <LabelList dataKey="value" position="top" formatter={(v) => num(Number(v), digits)} style={{ fontSize: 11, fill: '#003c73' }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ScatterPlot({ data, xLabel, yLabel, height = 280 }: {
  data: { name: string; x: number; y: number }[]
  xLabel: string
  yLabel: string
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ left: 0, right: 20, top: 10, bottom: 22 }}>
        <CartesianGrid stroke="#edf1f5" />
        <XAxis type="number" dataKey="x" name={xLabel} tick={axis} unit="%"
          label={{ value: xLabel, position: 'insideBottom', offset: -12, fontSize: 12, fill: '#5d6d7e' }} />
        <YAxis type="number" dataKey="y" name={yLabel} tick={axis} unit="%" width={48} />
        <ZAxis range={[70, 70]} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: '3 3' }}
          formatter={(v, n) => [`${num(Number(v), 1)}%`, String(n)]}
          labelFormatter={() => ''} />
        <Scatter data={data} fill={C.blue} fillOpacity={0.8} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
