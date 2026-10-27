// src/components/ui/index.jsx
// Small reusable UI primitives used across all pages

// ── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ size = 'md' }) {
  const s = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }[size]
  return (
    <div className={`${s} border-2 border-gray-200 border-t-brand-500 rounded-full animate-spin`} />
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────
export function StatCard({ label, value, sub, trend, trendUp, icon }) {
  const trendColor = trendUp ? 'text-red-500' : 'text-green-600'
  const trendArrow = trendUp ? '↑' : '↓'
  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</span>
        {icon && <span className="text-lg">{icon}</span>}
      </div>
      <div>
        <div className="text-2xl font-semibold text-gray-900 tracking-tight">{value}</div>
        <div className="flex items-center gap-2 mt-1">
          {sub && <span className="text-xs text-gray-400">{sub}</span>}
          {trend && (
            <span className={`text-xs font-medium ${trendColor}`}>
              {trendArrow} {trend}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────
export function EmptyState({ icon = '☁', title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-sm font-medium text-gray-900 mb-1">{title}</h3>
      {description && <p className="text-sm text-gray-400 max-w-xs mb-4">{description}</p>}
      {action}
    </div>
  )
}

// ── Page header ───────────────────────────────────────────────────────────────
export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
        {subtitle && <p className="text-sm text-gray-400 mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

// ── Section title ─────────────────────────────────────────────────────────────
export function SectionTitle({ children }) {
  return <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">{children}</h2>
}

// ── Alert banner ──────────────────────────────────────────────────────────────
export function AlertBanner({ type = 'info', children }) {
  const styles = {
    info:    'bg-blue-50  border-blue-200  text-blue-800',
    warning: 'bg-amber-50 border-amber-200 text-amber-800',
    success: 'bg-green-50 border-green-200 text-green-800',
    error:   'bg-red-50   border-red-200   text-red-800',
  }
  const icons = { info: 'ℹ', warning: '⚠', success: '✓', error: '✕' }
  return (
    <div className={`flex items-start gap-2 border rounded-lg px-4 py-3 text-sm ${styles[type]}`}>
      <span className="font-bold flex-shrink-0 mt-0.5">{icons[type]}</span>
      <span>{children}</span>
    </div>
  )
}

// ── Loading page ──────────────────────────────────────────────────────────────
export function LoadingPage() {
  return (
    <div className="flex items-center justify-center h-64">
      <Spinner size="lg" />
    </div>
  )
}

// ── Error page ────────────────────────────────────────────────────────────────
export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-3xl mb-3">⚠️</div>
      <p className="text-sm text-gray-600 mb-4">{message || 'Something went wrong'}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost">Try again</button>
      )}
    </div>
  )
}

// ── Modal ─────────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, footer }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="px-5 py-4 border-t border-gray-100 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  )
}
