// src/main.jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'

import AppShell      from './components/layout/AppShell'
import Login         from './pages/Login'
import Dashboard     from './pages/Dashboard'
import CostHistory   from './pages/CostHistory'
import IdleResources from './pages/IdleResources'
import AWSAccounts   from './pages/AWSAccounts'
import AlertSettings from './pages/AlertSettings'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry:      1,
      staleTime:  2 * 60 * 1000,
    },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          {/* All authenticated pages go inside AppShell (which checks auth) */}
          <Route element={<AppShell />}>
            <Route path="/dashboard"  element={<Dashboard />} />
            <Route path="/costs"      element={<CostHistory />} />
            <Route path="/resources"  element={<IdleResources />} />
            <Route path="/accounts"   element={<AWSAccounts />} />
            <Route path="/alerts"     element={<AlertSettings />} />
            <Route path="/billing"    element={<BillingStub />} />
          </Route>

          {/* Root redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
)

// Stub page for billing — wire up Stripe checkout here
function BillingStub() {
  const plans = [
    { name: 'Starter',  price: '₹2,999', accounts: 1,  features: ['Monthly reports', 'Email alerts'] },
    { name: 'Growth',   price: '₹5,999', accounts: 3,  features: ['Weekly reports', 'WhatsApp + email', 'Savings suggestions'], popular: true },
    { name: 'Business', price: '₹12,999',accounts: 10, features: ['Daily reports', 'Custom alerts', 'API access', 'Dedicated support'] },
  ]
  return (
    <div className="space-y-5">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-gray-900">Billing & Plans</h1>
        <p className="text-sm text-gray-400 mt-0.5">Upgrade or change your plan at any time</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {plans.map((p) => (
          <div key={p.name} className={`card relative ${p.popular ? 'border-brand-500 border-2' : ''}`}>
            {p.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-brand-500 text-white text-xs font-medium px-3 py-0.5 rounded-full">
                Most popular
              </div>
            )}
            <div className="mb-3">
              <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">{p.name}</p>
              <p className="text-2xl font-semibold text-gray-900 mt-1">{p.price}<span className="text-sm font-normal text-gray-400">/mo</span></p>
              <p className="text-xs text-gray-400 mt-0.5">{p.accounts} AWS account{p.accounts > 1 ? 's' : ''}</p>
            </div>
            <ul className="space-y-1.5 mb-4">
              {p.features.map((f) => (
                <li key={f} className="text-xs text-gray-600 flex items-center gap-1.5">
                  <span className="text-green-500">✓</span> {f}
                </li>
              ))}
            </ul>
            <button className={p.popular ? 'btn-primary w-full' : 'btn-ghost w-full'}>
              {p.popular ? 'Start free trial' : 'Choose plan'}
            </button>
          </div>
        ))}
      </div>
      <p className="text-xs text-center text-gray-400">
        All plans include a 30-day free trial · Annual billing saves 2 months · Cancel anytime
      </p>
    </div>
  )
}
