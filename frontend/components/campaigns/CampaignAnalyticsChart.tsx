'use client'

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { CampaignAnalytics } from '@/lib/types'

export function CampaignAnalyticsChart({ analytics }: { analytics: CampaignAnalytics }) {
  const data = [
    { stage: 'Sent', value: analytics.total_sent, color: '#6366f1' },
    { stage: 'Delivered', value: analytics.total_delivered, color: '#22c55e' },
    { stage: 'Opened', value: analytics.total_opened, color: '#f59e0b' },
    { stage: 'Clicked', value: analytics.total_clicked, color: '#f97316' },
    { stage: 'Converted', value: analytics.total_converted, color: '#ec4899' },
  ]

  return (
    <div className="h-72 rounded-xl border border-border bg-surface p-4">
      <h3 className="mb-4 font-semibold">Campaign Funnel</h3>
      <ResponsiveContainer width="100%" height="85%">
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
          <XAxis type="number" stroke="#737373" />
          <YAxis dataKey="stage" type="category" stroke="#a3a3a3" width={80} />
          <Tooltip cursor={{ fill: '#222' }} contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#f5f5f5' }} />
          <Bar dataKey="value" radius={[0, 6, 6, 0]}>
            {data.map((entry) => <Cell key={entry.stage} fill={entry.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
