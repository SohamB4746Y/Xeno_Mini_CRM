'use client'

import { useEffect, useState } from 'react'
import { MetricsGrid } from '@/components/dashboard/MetricsGrid'
import { RecentCampaigns } from '@/components/dashboard/RecentCampaigns'
import { AppShell } from '@/components/layout/AppShell'
import { api } from '@/lib/api'
import type { DashboardMetrics } from '@/lib/types'

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const data = await api.dashboard.getMetrics()
        setMetrics(data as DashboardMetrics)
        setError('')
      } catch (err) {
        console.error('Dashboard fetch error:', err)
        setError(
          'Unable to load dashboard data. The backend may be starting up — please refresh in 30 seconds.'
        )
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  return (
    <AppShell>
      <div className="space-y-6">
        {error && (
          <div className="rounded-lg border border-amber-700 bg-amber-900/20 p-4">
            <p className="text-sm text-amber-400">⚠️ {error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-2 text-xs text-amber-300 underline"
            >
              Click to retry
            </button>
          </div>
        )}
        {loading && !metrics ? (
          <div className="space-y-6">
            <div className="grid grid-cols-4 gap-4">
              {[0, 1, 2, 3].map((item) => (
                <div key={item} className="h-32 animate-pulse rounded-xl border border-border bg-surface" />
              ))}
            </div>
            <div className="h-80 animate-pulse rounded-xl border border-border bg-surface" />
          </div>
        ) : metrics ? (
          <>
            <MetricsGrid metrics={metrics} />
            <RecentCampaigns campaigns={metrics.recent_campaigns || []} />
          </>
        ) : null}
      </div>
    </AppShell>
  )
}
