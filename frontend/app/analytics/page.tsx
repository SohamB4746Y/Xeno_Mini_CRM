'use client'

import { useEffect, useState, useCallback } from 'react'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AppShell } from '@/components/layout/AppShell'
import { api } from '@/lib/api'

interface CampaignStat {
  campaign_id: string
  campaign_name: string
  channel: string
  status: string
  total_sent: number
  delivery_rate: number
  open_rate: number
  click_rate: number
  conversion_rate: number
  launched_at: string | null
}

const channelColors: Record<string, string> = {
  whatsapp: '#22c55e',
  email: '#6366f1',
  sms: '#a3a3a3',
  rcs: '#a855f7',
}

export default function AnalyticsPage() {
  const [stats, setStats] = useState<CampaignStat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError('')
      const data = (await api.campaigns.getAnalytics()) as CampaignStat[]
      setStats(data || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load analytics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const chartData = stats.map((s) => ({
    name: s.campaign_name.length > 18 ? s.campaign_name.slice(0, 18) + '…' : s.campaign_name,
    open_rate: Number(s.open_rate || 0),
    click_rate: Number(s.click_rate || 0),
    channel: s.channel,
  }))

  const avgOpen = stats.length ? stats.reduce((a, s) => a + Number(s.open_rate || 0), 0) / stats.length : 0
  const avgClick = stats.length ? stats.reduce((a, s) => a + Number(s.click_rate || 0), 0) / stats.length : 0
  const avgDelivery = stats.length ? stats.reduce((a, s) => a + Number(s.delivery_rate || 0), 0) / stats.length : 0
  const totalSent = stats.reduce((a, s) => a + (s.total_sent || 0), 0)

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold">Campaign Analytics</h2>
          <p className="text-sm text-neutral-500">Performance metrics across all ZURI campaigns.</p>
        </div>

        {error && (
          <div className="rounded-lg border border-amber-700 bg-amber-900/20 p-4">
            <p className="text-sm text-amber-400">⚠️ {error}</p>
            <button onClick={load} className="mt-2 text-xs text-amber-300 underline">Retry</button>
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-28 animate-pulse rounded-xl border border-border bg-surface" />
              ))}
            </div>
            <div className="h-72 animate-pulse rounded-xl border border-border bg-surface" />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: 'Total Sent', value: totalSent.toLocaleString(), sub: 'across all campaigns' },
                { label: 'Avg Delivery Rate', value: `${avgDelivery.toFixed(1)}%`, sub: 'successfully delivered' },
                { label: 'Avg Open Rate', value: `${avgOpen.toFixed(1)}%`, sub: 'messages opened' },
                { label: 'Avg Click Rate', value: `${avgClick.toFixed(1)}%`, sub: 'links clicked' },
              ].map((card) => (
                <div key={card.label} className="rounded-xl border border-border bg-surface p-5">
                  <div className="text-xs text-neutral-500">{card.label}</div>
                  <div className="mt-2 text-3xl font-semibold">{card.value}</div>
                  <div className="mt-1 text-xs text-neutral-500">{card.sub}</div>
                </div>
              ))}
            </div>

            {chartData.length > 0 && (
              <div className="rounded-xl border border-border bg-surface p-5">
                <h3 className="mb-4 font-semibold">Open Rate by Campaign</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={chartData} margin={{ left: 10, right: 10, bottom: 20 }}>
                    <XAxis dataKey="name" stroke="#737373" tick={{ fontSize: 11 }} angle={-20} textAnchor="end" />
                    <YAxis stroke="#737373" />
                    <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#f5f5f5' }} />
                    <Bar dataKey="open_rate" name="Open Rate %" radius={[6, 6, 0, 0]}>
                      {chartData.map((entry, i) => (
                        <Cell key={i} fill={channelColors[entry.channel] || '#6366f1'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="rounded-xl border border-border bg-surface">
              <div className="border-b border-border px-5 py-4">
                <h3 className="font-semibold">All Campaigns</h3>
              </div>
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="px-5 py-3 font-medium">Campaign</th>
                    <th className="px-5 py-3 font-medium">Channel</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Sent</th>
                    <th className="px-5 py-3 font-medium">Delivery</th>
                    <th className="px-5 py-3 font-medium">Open</th>
                    <th className="px-5 py-3 font-medium">Click</th>
                    <th className="px-5 py-3 font-medium">Conversion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {stats.map((s) => (
                    <tr key={s.campaign_id} className="text-neutral-300">
                      <td className="px-5 py-4 font-medium text-neutral-100">{s.campaign_name}</td>
                      <td className="px-5 py-4">
                        <span className="rounded-full bg-neutral-500/10 px-2 py-1 text-xs">{s.channel}</span>
                      </td>
                      <td className="px-5 py-4 text-xs">{s.status}</td>
                      <td className="px-5 py-4">{(s.total_sent || 0).toLocaleString()}</td>
                      <td className="px-5 py-4">{Number(s.delivery_rate || 0).toFixed(1)}%</td>
                      <td className="px-5 py-4">{Number(s.open_rate || 0).toFixed(1)}%</td>
                      <td className="px-5 py-4">{Number(s.click_rate || 0).toFixed(1)}%</td>
                      <td className="px-5 py-4">{Number(s.conversion_rate || 0).toFixed(1)}%</td>
                    </tr>
                  ))}
                  {!stats.length && (
                    <tr>
                      <td colSpan={8} className="px-5 py-10 text-center text-neutral-500">No campaign analytics yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
