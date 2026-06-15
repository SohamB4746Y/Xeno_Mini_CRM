import type { ChatMessage } from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = await response.json().catch(() => ({}))

  if (!response.ok) {
    const message = payload?.detail || payload?.message || `Request failed with ${response.status}`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }

  return payload as T
}

export const api = {
  dashboard: {
    getMetrics: () => request(`${BASE}/api/analytics/dashboard`),
  },
  customers: {
    list: (params?: { page?: number; page_size?: number; search?: string; tier?: string; city?: string }) => {
      const q = new URLSearchParams()
      Object.entries(params || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== '' && value !== 'all') q.set(key, String(value))
      })
      return request(`${BASE}/api/customers/?${q.toString()}`)
    },
  },
  segments: {
    list: () => request(`${BASE}/api/segments/`),
    create: (data: object) =>
      request(`${BASE}/api/segments/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    preview: (filter_rules: object) =>
      request(`${BASE}/api/segments/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filter_rules }),
      }),
  },
  campaigns: {
    list: () => request(`${BASE}/api/campaigns/`),
    get: (id: string) => request(`${BASE}/api/campaigns/${id}`),
    create: (data: object) =>
      request(`${BASE}/api/campaigns/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    launch: (id: string) =>
      request(`${BASE}/api/campaigns/${id}/launch`, {
        method: 'POST',
      }),
    getCommunications: (id: string) => request(`${BASE}/api/campaigns/${id}/communications`),
    getAnalytics: () => request(`${BASE}/api/analytics/campaigns`),
  },
  ai: {
    getInsights: () => request(`${BASE}/api/ai/insights`),
    chat: (message: string, conversation_history: ChatMessage[]) =>
      request(`${BASE}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, conversation_history }),
      }),
    quickLaunch: (quick_prompt: string) =>
      request(`${BASE}/api/ai/quick-launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quick_prompt, conversation_history: [] }),
      }),
  },
}
