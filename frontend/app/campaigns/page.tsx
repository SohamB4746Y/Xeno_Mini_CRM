'use client'

import { useEffect, useState } from 'react'
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

  function loadCampaigns() {
    api.campaigns
      .list()
      .then((data) => setCampaigns((data as CampaignListResponse).items || []))
      .catch((err) => setError(err.message || 'Could not load campaigns'))
  }

  useEffect(() => {
    loadCampaigns()
  }, [])

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
        <div>
          <h2 className="text-lg font-semibold">Campaigns</h2>
          <p className="text-sm text-neutral-500">Track every ZURI communication, from draft to conversion.</p>
        </div>
        {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}
        <div className="grid grid-cols-2 gap-4">
          {campaigns.map((campaign) => (
            <CampaignCard key={campaign.id} campaign={campaign} onLaunch={setLaunching} />
          ))}
        </div>
      </div>
      <LaunchCampaignModal campaign={launching} onClose={() => setLaunching(null)} onConfirm={confirmLaunch} loading={busy} />
    </AppShell>
  )
}
