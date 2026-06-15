'use client'

import { useEffect, useState, useCallback } from 'react'
import { CampaignCard } from '@/components/campaigns/CampaignCard'
import { LaunchCampaignModal } from '@/components/campaigns/LaunchCampaignModal'
import { AppShell } from '@/components/layout/AppShell'
import { api } from '@/lib/api'
import type { Campaign, CampaignListResponse } from '@/lib/types'

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [launching, setLaunching] = useState<Campaign | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const loadCampaigns = useCallback(async () => {
    try {
      setLoading(true)
      setError('')
      const data = (await api.campaigns.list()) as CampaignListResponse
      setCampaigns(data.items || [])
    } catch (err) {
      console.error('Campaigns fetch error:', err)
      setError(err instanceof Error ? err.message : 'Could not load campaigns')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadCampaigns()
  }, [loadCampaigns])

  async function confirmLaunch() {
    if (!launching) return
    setBusy(true)
    setError('')
    try {
      await api.campaigns.launch(launching.id)
      setLaunching(null)
      loadCampaigns()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Launch failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Campaigns</h2>
            <p className="text-sm text-neutral-500">Track every ZURI communication, from draft to conversion.</p>
          </div>
          {!loading && (
            <button
              onClick={loadCampaigns}
              className="rounded-lg border border-border px-4 py-2 text-sm text-neutral-300 hover:bg-surface"
            >
              Refresh
            </button>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-amber-700 bg-amber-900/20 p-4">
            <p className="text-sm text-amber-400">⚠️ {error}</p>
            <button onClick={loadCampaigns} className="mt-2 text-xs text-amber-300 underline">
              Click to retry
            </button>
          </div>
        )}

        {loading && !campaigns.length ? (
          <div className="grid grid-cols-2 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-64 animate-pulse rounded-xl border border-border bg-surface" />
            ))}
          </div>
        ) : campaigns.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface p-12 text-center">
            <p className="text-neutral-400">No campaigns yet. Use the AI Copilot to create your first campaign.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {campaigns.map((campaign) => (
              <CampaignCard key={campaign.id} campaign={campaign} onLaunch={setLaunching} />
            ))}
          </div>
        )}
      </div>
      <LaunchCampaignModal campaign={launching} onClose={() => setLaunching(null)} onConfirm={confirmLaunch} loading={busy} />
    </AppShell>
  )
}
