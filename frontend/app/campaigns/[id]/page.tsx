'use client'

import { useEffect, useState, useCallback } from 'react'
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
  try {
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return 'Invalid date'
  }
}

export default function CampaignDetailPage({ params }: PageProps) {
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [communications, setCommunications] = useState<Communication[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [launching, setLaunching] = useState(false)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError('')
      const data = (await api.campaigns.get(params.id)) as Campaign
      setCampaign(data)

      try {
        const commsData = (await api.campaigns.getCommunications(params.id)) as CommunicationListResponse
        setCommunications((commsData.items || []).slice(0, 20))
      } catch {
        setCommunications([])
      }
    } catch (err) {
      console.error('Campaign detail error:', err)
      setError(err instanceof Error ? err.message : 'Could not load campaign')
    } finally {
      setLoading(false)
    }
  }, [params.id])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (campaign?.status !== 'running') return
    const interval = window.setInterval(load, 8000)
    return () => window.clearInterval(interval)
  }, [campaign?.status, load])

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

  if (loading && !campaign) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="h-28 animate-pulse rounded-xl border border-border bg-surface" />
          <div className="grid grid-cols-2 gap-4">
            <div className="h-72 animate-pulse rounded-xl border border-border bg-surface" />
            <div className="h-72 animate-pulse rounded-xl border border-border bg-surface" />
          </div>
          <div className="h-48 animate-pulse rounded-xl border border-border bg-surface" />
        </div>
      </AppShell>
    )
  }

  if (error && !campaign) {
    return (
      <AppShell>
        <div className="flex flex-col items-center justify-center py-20">
          <div className="rounded-xl border border-amber-700 bg-amber-900/20 p-6 text-center">
            <p className="text-amber-400">⚠️ {error}</p>
            <button onClick={load} className="mt-3 rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-hover">
              Retry
            </button>
          </div>
        </div>
      </AppShell>
    )
  }

  if (!campaign) return null

  const analytics = campaign.analytics
  const totalDelivered = Number(analytics?.total_delivered || 0)
  const totalFailed = Number(analytics?.total_failed || 0)
  const pieData = [
    { name: 'Delivered', value: totalDelivered, color: '#22c55e' },
    { name: 'Failed', value: totalFailed, color: '#ef4444' },
  ]
  const hasPieData = totalDelivered > 0 || totalFailed > 0

  const stats = [
    ['Sent', Number(analytics?.total_sent || 0), `${Number(analytics?.delivery_rate || 0).toFixed(1)}% delivery`],
    ['Delivered', totalDelivered, `${Number(analytics?.open_rate || 0).toFixed(1)}% open`],
    ['Opened', Number(analytics?.total_opened || 0), 'engaged shoppers'],
    ['Clicked', Number(analytics?.total_clicked || 0), `${Number(analytics?.click_rate || 0).toFixed(1)}% click`],
    ['Converted', Number(analytics?.total_converted || 0), `${Number(analytics?.conversion_rate || 0).toFixed(1)}% conversion`],
    ['Failed', totalFailed, 'delivery failures'],
  ] as const

  return (
    <AppShell>
      <div className="space-y-6">
        {error && (
          <div className="rounded-lg border border-amber-700 bg-amber-900/20 p-4">
            <p className="text-sm text-amber-400">⚠️ {error}</p>
          </div>
        )}

        <section className="flex items-start justify-between rounded-xl border border-border bg-surface p-5">
          <div>
            <h2 className="text-2xl font-semibold">{campaign.name}</h2>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-primary/10 px-2 py-1 text-primary">{campaign.channel}</span>
              <span className="rounded-full bg-neutral-500/10 px-2 py-1 text-neutral-300">{campaign.status}</span>
              <span className="rounded-full bg-neutral-500/10 px-2 py-1 text-neutral-300">{formatDate(campaign.launched_at)}</span>
              <span className="rounded-full bg-neutral-500/10 px-2 py-1 text-neutral-300">{campaign.total_recipients || 0} recipients</span>
              {campaign.ai_generated_message && (
                <span className="rounded-full bg-indigo-500/10 px-2 py-1 text-indigo-300">AI Message</span>
              )}
            </div>
            {campaign.message_template && (
              <p className="mt-3 max-w-xl text-sm leading-relaxed text-neutral-400">{campaign.message_template}</p>
            )}
          </div>
          {campaign.status === 'draft' && (
            <button onClick={launch} disabled={launching} className="rounded-lg bg-primary px-5 py-3 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-60">
              {launching ? 'Launching...' : 'Launch Campaign'}
            </button>
          )}
        </section>

        {analytics ? (
          <>
            <div className="grid grid-cols-2 gap-4">
              <CampaignAnalyticsChart analytics={analytics} />
              <div className="h-72 rounded-xl border border-border bg-surface p-4">
                <h3 className="mb-4 font-semibold">Delivered vs Failed</h3>
                {hasPieData ? (
                  <ResponsiveContainer width="100%" height="85%">
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={4}>
                        {pieData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#f5f5f5' }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-[85%] items-center justify-center text-sm text-neutral-500">
                    No delivery data yet
                  </div>
                )}
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
        ) : (
          <div className="rounded-xl border border-border bg-surface p-8 text-center">
            <p className="text-neutral-500">Analytics will appear once the campaign has been launched and begins processing.</p>
          </div>
        )}

        <section className="rounded-xl border border-border bg-surface">
          <div className="border-b border-border px-5 py-4">
            <h3 className="font-semibold">Communications</h3>
          </div>
          {communications.length > 0 ? (
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
                {communications.map((comm) => (
                  <tr key={comm.id} className="text-neutral-300">
                    <td className="px-5 py-4 font-mono text-xs text-neutral-500">{comm.customer_id?.slice(0, 8) || '—'}</td>
                    <td className="px-5 py-4">{comm.status || '—'}</td>
                    <td className="px-5 py-4 text-neutral-500">{formatDate(comm.sent_at)}</td>
                    <td className="px-5 py-4 text-neutral-500">{formatDate(comm.delivered_at)}</td>
                    <td className="px-5 py-4 text-neutral-500">{formatDate(comm.clicked_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="px-5 py-10 text-center text-sm text-neutral-500">
              {campaign.status === 'draft' ? 'Communications will appear after launch.' : 'No communications recorded yet.'}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  )
}
