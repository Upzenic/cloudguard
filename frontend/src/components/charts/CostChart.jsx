// src/components/charts/CostChart.jsx
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts'
import { format, parseISO } from 'date-fns'

// ── Formatters ────────────────────────────────────────────────────────────────
const fmtINR = (v) =>
  v >= 100000
    ? `₹${(v / 100000).toFixed(1)}L`
    : v >= 1000
    ? `₹${(v / 1000).toFixed(0)}K`
    : `₹${v.toFixed(0)}`

const fmtMonth = (dateStr) => {
  try { return format(parseISO(dateStr), 'MMM yy') }
  catch { return dateStr }
}

// ── Custom tooltip ────────────────────────────────────────────────────────────
function CostTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2.5 text-xs">
      <p className="font-medium text-gray-600 mb-1">{fmtMonth(label)}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-gray-500">{p.name}:</span>
          <span className="font-medium text-gray-900">{fmtINR(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

// ── Monthly cost area chart ───────────────────────────────────────────────────
export function CostAreaChart({ data }) {
  const chartData = [...data]
    .sort((a, b) => new Date(a.period_start) - new Date(b.period_start))
    .map((d) => ({
      month:       d.period_start,
      'Actual (₹)':   d.total_inr,
      'Forecast (₹)': d.forecast_inr ?? undefined,
    }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#0066ff" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#0066ff" stopOpacity={0}    />
          </linearGradient>
          <linearGradient id="gradForecast" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}    />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
        <XAxis
          dataKey="month"
          tickFormatter={fmtMonth}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={fmtINR}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
          width={52}
        />
        <Tooltip content={<CostTooltip />} />
        <Area
          type="monotone"
          dataKey="Actual (₹)"
          stroke="#0066ff"
          strokeWidth={2}
          fill="url(#gradActual)"
          dot={{ r: 3, fill: '#0066ff', strokeWidth: 0 }}
          activeDot={{ r: 5 }}
        />
        <Area
          type="monotone"
          dataKey="Forecast (₹)"
          stroke="#f59e0b"
          strokeWidth={2}
          strokeDasharray="5 3"
          fill="url(#gradForecast)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

// ── Services breakdown bar chart ──────────────────────────────────────────────
export function ServicesBarChart({ services }) {
  const data = Object.entries(services ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)
    .map(([name, usd]) => ({
      name: name.replace('Amazon ', '').replace('AWS ', ''),
      '₹ Cost': Math.round(usd * 83.5),
    }))

  if (!data.length) return (
    <div className="flex items-center justify-center h-40 text-sm text-gray-400">
      No service data yet
    </div>
  )

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={fmtINR}
          tick={{ fontSize: 10, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={72}
          tick={{ fontSize: 10, fill: '#6b7280' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(v) => [fmtINR(v), 'Cost']}
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
        />
        <Bar dataKey="₹ Cost" fill="#0066ff" radius={[0, 4, 4, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  )
}
