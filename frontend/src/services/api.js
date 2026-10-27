// src/services/api.js
// All API calls in one place. Import this everywhere instead of calling fetch directly.

import axios from 'axios'
import { useAuthStore } from '../store/authStore'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 15000,
})

// Attach auth token to every request
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  // Local dev: use email header (remove before prod)
  const email = useAuthStore.getState().user?.email
  if (email && !token) {
    config.headers['X-Customer-Email'] = email
  }
  return config
})

// Handle 401 — redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const getDashboard = () =>
  api.get('/api/dashboard').then((r) => r.data)

// ── AWS Accounts ──────────────────────────────────────────────────────────────
export const addAWSAccount = (data) =>
  api.post('/api/aws-accounts', data).then((r) => r.data)

export const removeAWSAccount = (id) =>
  api.delete(`/api/aws-accounts/${id}`).then((r) => r.data)

export const generateExternalId = () =>
  api.post('/api/onboarding/external-id').then((r) => r.data)

// ── Alert config ──────────────────────────────────────────────────────────────
export const updateAlertConfig = (data) =>
  api.put('/api/alert-config', data).then((r) => r.data)

// ── Idle resources ────────────────────────────────────────────────────────────
export const dismissIdleResource = (id) =>
  api.post(`/api/idle-resources/${id}/dismiss`).then((r) => r.data)

// ── Payments ──────────────────────────────────────────────────────────────────
export const createStripeCheckout = (email, plan) =>
  api.post('/api/checkout/stripe', { email, plan }).then((r) => r.data)

// ── Registration ──────────────────────────────────────────────────────────────
export const registerCustomer = (data) =>
  api.post('/api/customers/register', data).then((r) => r.data)

export default api
