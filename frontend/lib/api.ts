import type { ChatMessage } from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'https://xenominicrm-production.up.railway.app'

async function safeFetch<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })
    if (!response.ok) {
      const errorText = await response.text().catch(() => '')
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }
    return response.json() as Promise<T>
  } catch (error) {
    console.error(`API call failed: ${url}`, error)
    throw error
  }
}

export const api = {
  dashboard: {
    getMetrics: () => safeFetch(`${BASE}/api/analytics/dashboard`),
  },
  customers: {
    list: (params?: { page?: number; page_size?: number; search?: string; tier?: string; city?: string }) => {
      const q = new URLSearchParams()
      Object.entries(params || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== '' && value !== 'all') q.set(key, String(value))
      })
      return safeFetch(`${BASE}/api/customers/?${q.toString()}`)
    },
  },
  segments: {
    list: () => safeFetch(`${BASE}/api/segments/`),
    create: (data: object) =>
      safeFetch(`${BASE}/api/segments/`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    preview: (filter_rules: object) =>
      safeFetch(`${BASE}/api/segments/preview`, {
        method: 'POST',
        body: JSON.stringify({ filter_rules }),
      }),
  },
  campaigns: {
    list: () => safeFetch(`${BASE}/api/campaigns/`),
    get: (id: string) => safeFetch(`${BASE}/api/campaigns/${id}`),
    create: (data: object) =>
      safeFetch(`${BASE}/api/campaigns/`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    launch: (id: string) =>
      safeFetch(`${BASE}/api/campaigns/${id}/launch`, {
        method: 'POST',
      }),
    getCommunications: (id: string) => safeFetch(`${BASE}/api/campaigns/${id}/communications`),
    getAnalytics: () => safeFetch(`${BASE}/api/analytics/campaigns`),
  },
  ai: {
    getInsights: () => safeFetch(`${BASE}/api/ai/insights`),
    chat: (message: string, conversation_history: ChatMessage[]) =>
      safeFetch(`${BASE}/api/ai/chat`, {
        method: 'POST',
        body: JSON.stringify({ message, conversation_history }),
      }),
    quickLaunch: (quick_prompt: string) =>
      safeFetch(`${BASE}/api/ai/quick-launch`, {
        method: 'POST',
        body: JSON.stringify({ quick_prompt, conversation_history: [] }),
      }),
  },
}
