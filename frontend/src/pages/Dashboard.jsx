// src/pages/Dashboard.jsx
import { useDashboard } from '../hooks/useDashboard'
import { StatCard, LoadingPage, ErrorState, PageHeader, AlertBanner, SectionTitle } from '../components/ui'
import { CostAreaChart, ServicesBarChart } from '../components/charts/CostChart'
import { format, parseISO } from 'date-fns'

const fmtINR = (v) =>
  v >= 100000
    ? `₹${(v / 100000).toFixed(1)}L`
    : `₹${(v ?? 0).toLocaleString('en-IN')}`

export default function Dashboard() {
  const { data, isLoading, isError, refetch } = useDashboard()

  if (isLoading) return <LoadingPage />
  if (isError)   return <ErrorState message="Failed to load dashboard data." onRetry={refetch} />

  const {
    customer,
    current_month_inr,
    cost_history,
    idle_resources,
    potential_savings_inr,
    alert_config,
    aws_accounts,
  } = data

  // Sort history: oldest → newest
  const sorted = [...(cost_history ?? [])].sort(
    (a, b) => new Date(a.period_start) - new Date(b.period_start)
  )

  const latestMonth   = sorted[sorted.length - 1]
  const previousMonth = sorted[sorted.length - 2]
  const latestServices= latestMonth?.services ?? {}

  // Month-over-month change
  let momTrend, momUp
  if (latestMonth && previousMonth && previousMonth.total_inr > 0) {
    const pct = ((latestMonth.total_inr - previousMonth.total_inr) / previousMonth.total_inr) * 100
    momTrend = `${Math.abs(pct).toFixed(1)}% vs last month`
    momUp    = pct > 0
  }

  // Budget usage
  const budget  = alert_config?.monthly_budget_inr ?? 0
  const budgetPct = budget > 0 ? Math.round((current_month_inr / budget) * 100) : 0
  const budgetColor = budgetPct >= 100 ? 'bg-red-500' : budgetPct >= 80 ? 'bg-amber-400' : 'bg-brand-500'

  const noAccounts = !aws_accounts?.length

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Good morning, ${customer.company_name} 👋`}
        subtitle="Here's your AWS spending at a glance"
      />

      {/* No accounts connected warning */}
      {noAccounts && (
        <AlertBanner type="warning">
          No AWS accounts connected yet.{' '}
          <a href="/accounts" className="underline font-medium">Add your first account →</a>
        </AlertBanner>
      )}

      {/* Stat row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="This month"
          value={fmtINR(current_month_inr)}
          sub={latestMonth ? `as of ${format(parseISO(latestMonth.period_start), 'MMM yyyy')}` : ''}
          trend={momTrend}
          trendUp={momUp}
          icon="₹"
        />
        <StatCard
          label="Month-end forecast"
          value={latestMonth?.forecast_inr ? fmtINR(latestMonth.forecast_inr) : '—'}
          sub="projected total"
          icon="📈"
        />
        <StatCard
          label="Potential savings"
          value={fmtINR(potential_savings_inr)}
          sub={`${idle_resources?.length ?? 0} idle resource${idle_resources?.length !== 1 ? 's' : ''}`}
          icon="💡"
        />
        <StatCard
          label="Budget used"
          value={budget > 0 ? `${budgetPct}%` : '—'}
          sub={budget > 0 ? `of ${fmtINR(budget)}` : 'Set a budget in Alerts'}
          icon="🎯"
        />
      </div>

      {/* Budget progress bar */}
      {budget > 0 && (
        <div className="card">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs font-medium text-gray-500">Monthly budget</span>
            <span className="text-xs font-medium text-gray-700">
              {fmtINR(current_month_inr)} / {fmtINR(budget)}
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${budgetColor}`}
              style={{ width: `${Math.min(budgetPct, 100)}%` }}
            />
          </div>
          {budgetPct >= 80 && (
            <p className={`text-xs mt-1.5 ${budgetPct >= 100 ? 'text-red-500' : 'text-amber-600'}`}>
              {budgetPct >= 100
                ? '🚨 Budget exceeded — check your idle resources'
                : `⚠️ ${budgetPct}% of monthly budget used`}
            </p>
          )}
        </div>
      )}

      {/* Cost trend + services breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <SectionTitle>Monthly cost trend</SectionTitle>
          {sorted.length > 0
            ? <CostAreaChart data={sorted} />
            : <div className="h-40 flex items-center justify-center text-sm text-gray-400">
                No cost data yet — check back after first sync
              </div>
          }
        </div>

        <div className="card">
          <SectionTitle>Top services — {latestMonth ? format(parseISO(latestMonth.period_start), 'MMM yyyy') : 'latest month'}</SectionTitle>
          <ServicesBarChart services={latestServices} />
        </div>
      </div>

      {/* Idle resources preview */}
      {idle_resources?.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <SectionTitle>Idle resources found</SectionTitle>
            <a href="/resources" className="text-xs text-brand-500 font-medium hover:text-brand-600">
              View all →
            </a>
          </div>
          <div className="divide-y divide-gray-50">
            {idle_resources.slice(0, 5).map((r) => (
              <div key={r.id} className="flex items-center justify-between py-2.5">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-gray-500 bg-gray-50 px-2 py-0.5 rounded">
                    {r.type.toUpperCase()}
                  </span>
                  <div>
                    <p className="text-sm text-gray-800 font-medium">{r.name ?? r.resource_id}</p>
                    <p className="text-xs text-gray-400">{r.region} · {r.resource_id}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-red-500">{fmtINR(r.monthly_inr)}/mo</p>
                  {r.avg_cpu_7d !== null && (
                    <p className="text-xs text-gray-400">{r.avg_cpu_7d}% avg CPU</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AWS accounts status */}
      {aws_accounts?.length > 0 && (
        <div className="card">
          <SectionTitle>Connected accounts</SectionTitle>
          <div className="space-y-2">
            {aws_accounts.map((acc) => (
              <div key={acc.id} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2.5">
                  <div className={`w-2 h-2 rounded-full ${acc.sync_error ? 'bg-red-400' : 'bg-green-400'}`} />
                  <span className="text-sm text-gray-800">{acc.name ?? acc.account_id}</span>
                  <span className="font-mono text-xs text-gray-400">{acc.account_id}</span>
                </div>
                <div className="text-right">
                  {acc.sync_error
                    ? <span className="badge-red">Error</span>
                    : <span className="text-xs text-gray-400">
                        {acc.last_synced ? `Synced ${format(new Date(acc.last_synced), 'MMM d HH:mm')}` : 'Pending first sync'}
                      </span>
                  }
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
