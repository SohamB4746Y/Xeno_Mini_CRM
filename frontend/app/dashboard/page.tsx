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

  useEffect(() => {
    api.dashboard
      .getMetrics()
      .then((data) => setMetrics(data as DashboardMetrics))
      .catch((err) => setError(err.message || 'Could not load dashboard'))
  }, [])

  return (
    <AppShell>
      <div className="space-y-6">
        {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}
        {!metrics ? (
          <div className="space-y-6">
            <div className="grid grid-cols-4 gap-4">
              {[0, 1, 2, 3].map((item) => (
                <div key={item} className="h-32 animate-pulse rounded-xl border border-border bg-surface" />
              ))}
            </div>
            <div className="h-80 animate-pulse rounded-xl border border-border bg-surface" />
          </div>
        ) : (
          <>
            <MetricsGrid metrics={metrics} />
            <RecentCampaigns campaigns={metrics.recent_campaigns || []} />
          </>
        )}
      </div>
    </AppShell>
  )
}
