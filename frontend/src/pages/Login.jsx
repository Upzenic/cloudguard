// src/pages/Login.jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { registerCustomer } from '../services/api'

export default function Login() {
  const navigate  = useNavigate()
  const { login } = useAuthStore()

  const [mode, setMode]   = useState('login')   // login | register
  const [form, setForm]   = useState({ email: '', company_name: '', plan: 'growth' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (mode === 'register') {
        await registerCustomer({ email: form.email, company_name: form.company_name, plan: form.plan })
      }
      // In prod: Cognito auth flow. For dev: email-only login
      login({ email: form.email, company_name: form.company_name, plan: form.plan }, null)
      navigate('/dashboard')
    } catch (e) {
      setError(e.response?.data?.detail ?? 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-1 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-brand-500 text-white text-xl font-bold mb-4">
            CG
          </div>
          <h1 className="text-xl font-semibold text-gray-900">CloudGuard</h1>
          <p className="text-sm text-gray-400 mt-1">AWS cost monitoring for startups</p>
        </div>

        {/* Card */}
        <div className="card shadow-sm">
          {/* Mode toggle */}
          <div className="flex rounded-lg bg-gray-100 p-1 mb-5">
            {['login', 'register'].map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors capitalize ${
                  mode === m ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500'
                }`}
              >
                {m === 'login' ? 'Sign in' : 'Start free trial'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            {mode === 'register' && (
              <div>
                <label className="label">Company name</label>
                <input
                  className="input"
                  placeholder="Acme Technologies"
                  value={form.company_name}
                  onChange={(e) => setForm((f) => ({ ...f, company_name: e.target.value }))}
                  required
                />
              </div>
            )}

            <div>
              <label className="label">Work email</label>
              <input
                type="email"
                className="input"
                placeholder="you@company.com"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                required
              />
            </div>

            {mode === 'register' && (
              <div>
                <label className="label">Plan</label>
                <select
                  className="input"
                  value={form.plan}
                  onChange={(e) => setForm((f) => ({ ...f, plan: e.target.value }))}
                >
                  <option value="starter">Starter — ₹2,999/month (1 account)</option>
                  <option value="growth">Growth — ₹5,999/month (3 accounts)</option>
                  <option value="business">Business — ₹12,999/month (10 accounts)</option>
                </select>
              </div>
            )}

            {error && (
              <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>
            )}

            <button type="submit" className="btn-primary w-full py-2.5 mt-1" disabled={loading}>
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Start 30-day free trial'}
            </button>
          </form>

          {mode === 'register' && (
            <p className="text-xs text-center text-gray-400 mt-3">
              No credit card required during trial. Cancel anytime.
            </p>
          )}
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
            className="text-brand-500 hover:underline"
          >
            {mode === 'login' ? 'Start free trial' : 'Sign in'}
          </button>
        </p>
      </div>
    </div>
  )
}
