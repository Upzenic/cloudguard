// src/pages/AlertSettings.jsx
import { useState, useEffect } from 'react'
import { useDashboard, useUpdateAlertConfig } from '../hooks/useDashboard'
import { PageHeader, LoadingPage, ErrorState, AlertBanner, SectionTitle } from '../components/ui'

export default function AlertSettings() {
  const { data, isLoading, isError, refetch } = useDashboard()
  const updateConfig = useUpdateAlertConfig()

  const [form, setForm] = useState({
    monthly_budget_inr: 100000,
    alert_at_percent:   80,
    alert_email:        true,
    alert_whatsapp:     false,
  })
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (data?.alert_config) {
      setForm({
        monthly_budget_inr: data.alert_config.monthly_budget_inr ?? 100000,
        alert_at_percent:   data.alert_config.alert_at_percent   ?? 80,
        alert_email:        data.alert_config.alert_email        ?? true,
        alert_whatsapp:     data.alert_config.alert_whatsapp     ?? false,
      })
    }
  }, [data])

  if (isLoading) return <LoadingPage />
  if (isError)   return <ErrorState message="Failed to load alert config." onRetry={refetch} />

  const handleSave = async () => {
    await updateConfig.mutateAsync(form)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const alertThreshold = Math.round(form.monthly_budget_inr * form.alert_at_percent / 100)

  return (
    <div className="space-y-5 max-w-xl">
      <PageHeader
        title="Alert Settings"
        subtitle="Set your monthly budget and choose how you want to be notified"
      />

      {saved && <AlertBanner type="success">Settings saved successfully.</AlertBanner>}

      {/* Budget */}
      <div className="card space-y-4">
        <SectionTitle>Monthly budget</SectionTitle>

        <div>
          <label className="label">Monthly AWS budget (₹)</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">₹</span>
            <input
              type="number"
              className="input pl-7"
              value={form.monthly_budget_inr}
              min={1000}
              step={1000}
              onChange={(e) => setForm((f) => ({ ...f, monthly_budget_inr: Number(e.target.value) }))}
            />
          </div>
          <p className="text-xs text-gray-400 mt-1">
            We'll alert you when your spend reaches {form.alert_at_percent}% of this amount (₹{alertThreshold.toLocaleString('en-IN')}).
          </p>
        </div>

        <div>
          <label className="label">Alert threshold</label>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={50} max={100} step={5}
              value={form.alert_at_percent}
              onChange={(e) => setForm((f) => ({ ...f, alert_at_percent: Number(e.target.value) }))}
              className="flex-1 accent-brand-500"
            />
            <span className="text-sm font-medium text-gray-700 w-10 text-right">
              {form.alert_at_percent}%
            </span>
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-0.5">
            <span>50%</span><span>75%</span><span>100%</span>
          </div>
        </div>
      </div>

      {/* Channels */}
      <div className="card space-y-3">
        <SectionTitle>Notification channels</SectionTitle>

        <label className="flex items-center justify-between cursor-pointer">
          <div>
            <p className="text-sm font-medium text-gray-900">Email alerts</p>
            <p className="text-xs text-gray-400">Sent to {data?.customer?.email}</p>
          </div>
          <div
            onClick={() => setForm((f) => ({ ...f, alert_email: !f.alert_email }))}
            className={`w-10 h-5.5 rounded-full transition-colors cursor-pointer flex items-center px-0.5 ${
              form.alert_email ? 'bg-brand-500' : 'bg-gray-200'
            }`}
          >
            <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform ${form.alert_email ? 'translate-x-[18px]' : 'translate-x-0'}`} />
          </div>
        </label>

        <div className="border-t border-gray-50 pt-3">
          <label className="flex items-center justify-between cursor-pointer">
            <div>
              <p className="text-sm font-medium text-gray-900">WhatsApp alerts</p>
              <p className="text-xs text-gray-400">Instant alerts on your phone</p>
            </div>
            <div
              onClick={() => setForm((f) => ({ ...f, alert_whatsapp: !f.alert_whatsapp }))}
              className={`w-10 h-5.5 rounded-full transition-colors cursor-pointer flex items-center px-0.5 ${
                form.alert_whatsapp ? 'bg-brand-500' : 'bg-gray-200'
              }`}
            >
              <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform ${form.alert_whatsapp ? 'translate-x-[18px]' : 'translate-x-0'}`} />
            </div>
          </label>
          {form.alert_whatsapp && (
            <div className="mt-2">
              <label className="label">WhatsApp number</label>
              <input
                className="input font-mono"
                placeholder="+919876543210"
                defaultValue={data?.customer?.whatsapp_number ?? ''}
              />
              <p className="text-xs text-gray-400 mt-1">Include country code. You must opt-in to Twilio's WhatsApp sandbox first.</p>
            </div>
          )}
        </div>
      </div>

      {/* Summary preview */}
      <div className="card bg-gray-50">
        <SectionTitle>What will happen</SectionTitle>
        <ul className="text-sm text-gray-600 space-y-1.5">
          <li>✓ Daily data sync at <strong>06:00 IST</strong></li>
          <li>✓ Alert when spend exceeds <strong>₹{alertThreshold.toLocaleString('en-IN')}</strong> ({form.alert_at_percent}% of ₹{form.monthly_budget_inr.toLocaleString('en-IN')})</li>
          {form.alert_email    && <li>✓ Email to <strong>{data?.customer?.email}</strong></li>}
          {form.alert_whatsapp && <li>✓ WhatsApp message to your number</li>}
          <li>✓ Weekly digest every <strong>Monday at 08:00 IST</strong></li>
        </ul>
      </div>

      <button
        className="btn-primary w-full py-2.5"
        onClick={handleSave}
        disabled={updateConfig.isPending}
      >
        {updateConfig.isPending ? 'Saving…' : 'Save alert settings'}
      </button>
    </div>
  )
}
