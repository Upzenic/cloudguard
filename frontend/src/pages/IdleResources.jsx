// src/pages/IdleResources.jsx
import { useState } from 'react'
import { useDashboard, useDismissResource } from '../hooks/useDashboard'
import {
  PageHeader, LoadingPage, ErrorState,
  EmptyState, SectionTitle, Modal, AlertBanner
} from '../components/ui'

const fmtINR = (v) => `₹${(v ?? 0).toLocaleString('en-IN')}`

const RESOURCE_ICONS = {
  ec2:         '🖥',
  ebs:         '💾',
  eip:         '🔗',
  rds:         '🗄',
  nat_gateway: '🌐',
}

const RESOURCE_LABELS = {
  ec2:         'EC2 Instance',
  ebs:         'EBS Volume (unattached)',
  eip:         'Elastic IP (unused)',
  rds:         'RDS Instance',
  nat_gateway: 'NAT Gateway',
}

export default function IdleResources() {
  const { data, isLoading, isError, refetch } = useDashboard()
  const dismiss = useDismissResource()
  const [confirmId, setConfirmId] = useState(null)
  const [filter, setFilter]       = useState('all')

  if (isLoading) return <LoadingPage />
  if (isError)   return <ErrorState message="Failed to load resources." onRetry={refetch} />

  const allResources = data?.idle_resources ?? []
  const filtered     = filter === 'all' ? allResources : allResources.filter((r) => r.type === filter)
  const totalSavings = allResources.reduce((s, r) => s + (r.monthly_inr ?? 0), 0)

  const types = [...new Set(allResources.map((r) => r.type))]

  const handleDismiss = async () => {
    await dismiss.mutateAsync(confirmId)
    setConfirmId(null)
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Idle Resources"
        subtitle="Resources running but barely used — review and stop them to save money"
      />

      {allResources.length > 0 && (
        <AlertBanner type="warning">
          Found <strong>{allResources.length} idle resource{allResources.length !== 1 ? 's' : ''}</strong> costing{' '}
          <strong>{fmtINR(totalSavings)}/month</strong>. Stopping or deleting them could save this amount immediately.
        </AlertBanner>
      )}

      {/* Filter tabs */}
      {types.length > 1 && (
        <div className="flex gap-1.5 flex-wrap">
          {['all', ...types].map((t) => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                filter === t
                  ? 'bg-brand-500 text-white border-brand-500'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
              }`}
            >
              {t === 'all' ? `All (${allResources.length})` : `${RESOURCE_ICONS[t] ?? ''} ${RESOURCE_LABELS[t] ?? t}`}
            </button>
          ))}
        </div>
      )}

      {/* Resource list */}
      {filtered.length === 0 ? (
        <EmptyState
          icon="✅"
          title="No idle resources found"
          description="Your AWS accounts look clean. We'll scan again tonight and alert you if anything changes."
        />
      ) : (
        <div className="card p-0 overflow-hidden">
          <div className="divide-y divide-gray-50">
            {filtered.map((r) => (
              <div key={r.id} className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors">
                {/* Icon */}
                <div className="text-2xl w-8 text-center flex-shrink-0">
                  {RESOURCE_ICONS[r.type] ?? '☁'}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900">
                      {r.name ?? r.resource_id}
                    </span>
                    <span className="font-mono text-xs text-gray-400">{r.resource_id}</span>
                    <span className="badge-gray">{RESOURCE_LABELS[r.type] ?? r.type}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                    <span className="text-xs text-gray-400">📍 {r.region}</span>
                    {r.avg_cpu_7d !== null && r.avg_cpu_7d !== undefined && (
                      <span className="text-xs text-gray-400">
                        CPU avg: <span className="text-amber-600 font-medium">{r.avg_cpu_7d}%</span> over 7 days
                      </span>
                    )}
                  </div>
                </div>

                {/* Cost */}
                <div className="text-right flex-shrink-0">
                  <div className="text-sm font-semibold text-red-500">{fmtINR(r.monthly_inr)}</div>
                  <div className="text-xs text-gray-400">per month</div>
                </div>

                {/* Action */}
                <button
                  onClick={() => setConfirmId(r.id)}
                  className="btn-ghost text-xs flex-shrink-0"
                >
                  Dismiss
                </button>
              </div>
            ))}
          </div>

          {/* Footer summary */}
          <div className="px-5 py-3 bg-gray-50 border-t border-gray-100 flex justify-between items-center">
            <span className="text-xs text-gray-500">{filtered.length} resource{filtered.length !== 1 ? 's' : ''} shown</span>
            <span className="text-xs font-medium text-red-500">
              Total waste: {fmtINR(filtered.reduce((s, r) => s + (r.monthly_inr ?? 0), 0))}/month
            </span>
          </div>
        </div>
      )}

      {/* Dismiss confirm modal */}
      <Modal
        open={!!confirmId}
        onClose={() => setConfirmId(null)}
        title="Dismiss idle resource?"
        footer={
          <>
            <button className="btn-ghost" onClick={() => setConfirmId(null)}>Cancel</button>
            <button
              className="btn-primary"
              onClick={handleDismiss}
              disabled={dismiss.isPending}
            >
              {dismiss.isPending ? 'Dismissing…' : 'Yes, dismiss'}
            </button>
          </>
        }
      >
        <p className="text-sm text-gray-600">
          This removes the resource from your idle list. CloudGuard will still scan for it again on the next daily run
          unless you actually stop or delete it in AWS.
        </p>
        <p className="text-sm text-gray-500 mt-2">
          To permanently stop the cost, go to your AWS console and stop or terminate the resource.
        </p>
      </Modal>
    </div>
  )
}
