'use client'

import { Filter, Send, TrendingUp, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { DashboardMetrics } from '@/lib/types'

function AnimatedNumber({ value, suffix = '' }: { value: number; suffix?: string }) {
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    const duration = 700
    const startedAt = performance.now()
    const tick = (now: number) => {
      const progress = Math.min((now - startedAt) / duration, 1)
      setDisplay(Math.round(value * progress))
      if (progress < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [value])

  return (
    <>
      {display.toLocaleString()}
      {suffix}
    </>
  )
}

export function MetricsGrid({ metrics }: { metrics: DashboardMetrics | null }) {
  const cards = [
    {
      label: 'Total Customers',
      value: metrics?.total_customers || 0,
      icon: Users,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
      suffix: '',
    },
    {
      label: 'Active Segments',
      value: metrics?.active_segments || 0,
      icon: Filter,
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
      suffix: '',
    },
    {
      label: 'Campaigns This Month',
      value: metrics?.campaigns_this_month || 0,
      icon: Send,
      color: 'text-green-400',
      bg: 'bg-green-500/10',
      suffix: '',
    },
    {
      label: 'Avg Open Rate',
      value: Math.round(Number(metrics?.average_open_rate || 0)),
      icon: TrendingUp,
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
      suffix: '%',
    },
  ]

  return (
    <div className="grid grid-cols-4 gap-4">
      {cards.map((card) => {
        const Icon = card.icon
        return (
          <div key={card.label} className="rounded-xl border border-border bg-surface p-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm text-neutral-500">{card.label}</div>
                <div className="mt-3 text-3xl font-semibold text-neutral-100">
                  <AnimatedNumber value={card.value} suffix={card.suffix} />
                </div>
              </div>
              <div className={`rounded-lg ${card.bg} p-3 ${card.color}`}>
                <Icon className="h-5 w-5" />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
