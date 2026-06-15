'use client'

import { useEffect, useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { CampaignAnalyticsChart } from '@/components/campaigns/CampaignAnalyticsChart'
import { AppShell } from '@/components/layout/AppShell'
import { api } from '@/lib/api'
import type { Campaign, Communication, CommunicationListResponse } from '@/lib/types'

type PageProps = {
  params: {
    id: string
  }
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'Not available'
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export default function CampaignDetailPage({ params }: PageProps) {
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [communications, setCommunications] = useState<Communication[]>([])
  const [error, setError] = useState('')
  const [launching, setLaunching] = useState(false)

  function load() {
    api.campaigns
      .get(params.id)
      .then((data) => setCampaign(data as Campaign))
      .catch((err) => setError(err.message || 'Could not load campaign'))
    api.campaigns
      .getCommunications(params.id)
      .then((data) => setCommunications(((data as CommunicationListResponse).items || []).slice(0, 20)))
      .catch(() => undefined)
  }

  useEffect(() => {
    load()
  }, [params.id])

  useEffect(() => {
    if (campaign?.status !== 'running') return
    const interval = window.setInterval(load, 5000)
    return () => window.clearInterval(interval)
  }, [campaign?.status, params.id])

  async function launch() {
    setLaunching(true)
    setError('')
    try {
      await api.campaigns.launch(params.id)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Launch failed')
    } finally {
      setLaunching(false)
    }
  }

  const analytics = campaign?.analytics
  const pieData = [
    { name: 'Delivered', value: analytics?.total_delivered || 0, color: '#22c55e' },
    { name: 'Failed', value: analytics?.total_failed || 0, color: '#ef4444' },
  ]
  const stats = [
    ['Sent', analytics?.total_sent || 0, `${Number(analytics?.delivery_rate || 0).toFixed(1)}% delivery`],
    ['Delivered', analytics?.total_delivered || 0, `${Number(analytics?.open_rate || 0).toFixed(1)}% open`],
    ['Opened', analytics?.total_opened || 0, 'engaged shoppers'],
    ['Clicked', analytics?.total_clicked || 0, `${Number(analytics?.click_rate || 0).toFixed(1)}% click`],
    ['Converted', analytics?.total_converted || 0, `${Number(analytics?.conversion_rate || 0).toFixed(1)}% conversion`],
    ['Failed', analytics?.total_failed || 0, 'delivery failures'],
  ]

  return (
    <AppShell>
      {!campaign ? (
        <div className="h-96 animate-pulse rounded-xl border border-border bg-surface" />
      ) : (
        <div className="space-y-6">
          {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

          <section className="flex items-start justify-between rounded-xl border border-border bg-surface p-5">
            <div>
              <h2 className="text-2xl font-semibold">{campaign.name}</h2>
              <div className="mt-3 flex gap-2 text-xs">
                <span className="rounded-full bg-primary/10 px-2 py-1 text-primary">{campaign.channel}</span>
                <span className="rounded-full bg-neutral-500/10 px-2 py-1 text-neutral-300">{campaign.status}</span>
                <span className="rounded-full bg-neutral-500/10 px-2 py-1 text-neutral-300">{formatDate(campaign.launched_at)}</span>
              </div>
            </div>
            {campaign.status === 'draft' && (
              <button onClick={launch} disabled={launching} className="rounded-lg bg-primary px-5 py-3 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-60">
                {launching ? 'Launching...' : 'Launch Campaign'}
              </button>
            )}
          </section>

          {analytics && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <CampaignAnalyticsChart analytics={analytics} />
                <div className="h-72 rounded-xl border border-border bg-surface p-4">
                  <h3 className="mb-4 font-semibold">Delivered vs Failed</h3>
                  <ResponsiveContainer width="100%" height="85%">
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={4}>
                        {pieData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#f5f5f5' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="grid grid-cols-6 gap-3">
                {stats.map(([label, value, helper]) => (
                  <div key={label} className="rounded-xl border border-border bg-surface p-4">
                    <div className="text-xs text-neutral-500">{label}</div>
                    <div className="mt-2 text-2xl font-semibold">{Number(value).toLocaleString()}</div>
                    <div className="mt-1 text-xs text-neutral-500">{helper}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          <section className="rounded-xl border border-border bg-surface">
            <div className="border-b border-border px-5 py-4">
              <h3 className="font-semibold">Communications</h3>
            </div>
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Customer</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Sent</th>
                  <th className="px-5 py-3 font-medium">Delivered</th>
                  <th className="px-5 py-3 font-medium">Clicked</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {communications.map((communication) => (
                  <tr key={communication.id} className="text-neutral-300">
                    <td className="px-5 py-4 font-mono text-xs text-neutral-500">{communication.customer_id.slice(0, 8)}</td>
                    <td className="px-5 py-4">{communication.status}</td>
                    <td className="px-5 py-4 text-neutral-500">{formatDate(communication.sent_at)}</td>
                    <td className="px-5 py-4 text-neutral-500">{formatDate(communication.delivered_at)}</td>
                    <td className="px-5 py-4 text-neutral-500">{formatDate(communication.clicked_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </AppShell>
  )
}
