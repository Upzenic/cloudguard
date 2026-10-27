// src/pages/CostHistory.jsx
import { useDashboard } from '../hooks/useDashboard'
import { PageHeader, LoadingPage, ErrorState, EmptyState, SectionTitle } from '../components/ui'
import { CostAreaChart, ServicesBarChart } from '../components/charts/CostChart'
import { format, parseISO } from 'date-fns'
import { useState } from 'react'

const fmtINR  = (v) => `₹${(v ?? 0).toLocaleString('en-IN')}`
const fmtUSD  = (v) => `$${(v ?? 0).toFixed(2)}`

export default function CostHistory() {
  const { data, isLoading, isError, refetch } = useDashboard()
  const [selected, setSelected] = useState(0)   // index into sorted history

  if (isLoading) return <LoadingPage />
  if (isError)   return <ErrorState message="Failed to load cost history." onRetry={refetch} />

  const sorted = [...(data?.cost_history ?? [])].sort(
    (a, b) => new Date(b.period_start) - new Date(a.period_start)
  )

  if (sorted.length === 0) {
    return (
      <>
        <PageHeader title="Cost History" subtitle="Monthly spending breakdown" />
        <EmptyState
          icon="₹"
          title="No cost data yet"
          description="Connect an AWS account and data will appear after the first nightly sync (06:00 IST)."
        />
      </>
    )
  }

  const current = sorted[selected]
  const services = current?.services ?? {}

  return (
    <div className="space-y-5">
      <PageHeader title="Cost History" subtitle="Monthly spending breakdown per AWS account" />

      {/* Trend chart */}
      <div className="card">
        <SectionTitle>Spending trend</SectionTitle>
        <CostAreaChart data={[...sorted].reverse()} />
      </div>

      {/* Month selector + details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Month list */}
        <div className="card p-0 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100">
            <SectionTitle>Monthly breakdown</SectionTitle>
          </div>
          <div className="divide-y divide-gray-50">
            {sorted.map((period, i) => {
              const prev       = sorted[i + 1]
              const changePct  = prev && prev.total_inr > 0
                ? ((period.total_inr - prev.total_inr) / prev.total_inr) * 100
                : null

              return (
                <button
                  key={period.period_start}
                  onClick={() => setSelected(i)}
                  className={`w-full text-left flex items-center justify-between px-5 py-3 transition-colors ${
                    selected === i ? 'bg-brand-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <div>
                    <p className={`text-sm font-medium ${selected === i ? 'text-brand-600' : 'text-gray-900'}`}>
                      {format(parseISO(period.period_start), 'MMMM yyyy')}
                    </p>
                    {period.forecast_inr && i === 0 && (
                      <p className="text-xs text-amber-600">
                        Projected: {fmtINR(period.forecast_inr)}
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-gray-900">{fmtINR(period.total_inr)}</p>
                    {changePct !== null && (
                      <p className={`text-xs ${changePct > 0 ? 'text-red-500' : 'text-green-600'}`}>
                        {changePct > 0 ? '↑' : '↓'} {Math.abs(changePct).toFixed(1)}%
                      </p>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Services breakdown */}
        <div className="space-y-4">
          <div className="card">
            <SectionTitle>
              {format(parseISO(current.period_start), 'MMMM yyyy')} — by service
            </SectionTitle>
            <ServicesBarChart services={services} />
          </div>

          {/* Raw numbers table */}
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-2.5 font-medium text-gray-500">Service</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-500">USD</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-500">INR</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {Object.entries(services)
                  .sort(([, a], [, b]) => b - a)
                  .map(([name, usd]) => (
                    <tr key={name} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-gray-700 truncate max-w-[160px]">
                        {name.replace('Amazon ', '').replace('AWS ', '')}
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-gray-600">{fmtUSD(usd)}</td>
                      <td className="px-4 py-2 text-right font-mono text-gray-800 font-medium">
                        {fmtINR(usd * 83.5)}
                      </td>
                    </tr>
                  ))}
                <tr className="bg-gray-50 font-medium">
                  <td className="px-4 py-2.5 text-gray-900">Total</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{fmtUSD(current.total_usd)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{fmtINR(current.total_inr)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
