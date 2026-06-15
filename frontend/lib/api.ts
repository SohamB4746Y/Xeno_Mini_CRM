import type { ChatMessage } from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'https://xenominicrm-production.up.railway.app'

const MAX_RETRIES = 2
const RETRY_DELAYS = [1000, 2500]
const REQUEST_TIMEOUT = 25000

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function safeFetch<T>(url: string, options?: RequestInit, retries = MAX_RETRIES): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT)

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })
    clearTimeout(timeout)

    if (!response.ok) {
      const errorText = await response.text().catch(() => '')
      const message = `HTTP ${response.status}: ${errorText.slice(0, 200)}`

      if (retries > 0 && (response.status >= 500 || response.status === 429)) {
        const delay = RETRY_DELAYS[MAX_RETRIES - retries] || 2000
        console.warn(`[API] Retrying ${url} in ${delay}ms (${retries} left)`)
        await sleep(delay)
        return safeFetch<T>(url, options, retries - 1)
      }

      throw new Error(message)
    }

    return response.json() as Promise<T>
  } catch (error) {
    clearTimeout(timeout)

    if (error instanceof DOMException && error.name === 'AbortError') {
      if (retries > 0) {
        const delay = RETRY_DELAYS[MAX_RETRIES - retries] || 2000
        console.warn(`[API] Timeout, retrying ${url} in ${delay}ms`)
        await sleep(delay)
        return safeFetch<T>(url, options, retries - 1)
      }
      throw new Error('Request timed out. The backend may still be starting up — please try again.')
    }

    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      if (retries > 0) {
        const delay = RETRY_DELAYS[MAX_RETRIES - retries] || 2000
        console.warn(`[API] Network error, retrying ${url} in ${delay}ms`)
        await sleep(delay)
        return safeFetch<T>(url, options, retries - 1)
      }
      throw new Error('Unable to reach the server. Please check your connection and try again.')
    }

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
