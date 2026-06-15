'use client'

import clsx from 'clsx'
import type { OpportunityCard } from '@/lib/types'

const priorityClasses = {
  high: 'border-red-500/50 bg-red-500/5 text-red-300',
  medium: 'border-amber-500/50 bg-amber-500/5 text-amber-300',
  low: 'border-neutral-600 bg-neutral-500/5 text-neutral-300',
}

type InsightCardProps = {
  insight: OpportunityCard
  onAsk: (prompt: string) => void
  onQuickLaunch: (prompt: string) => void
  disabled?: boolean
}

export function InsightCard({ insight, onAsk, onQuickLaunch, disabled }: InsightCardProps) {
  return (
    <div className={clsx('rounded-xl border p-3', priorityClasses[insight.priority])}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{insight.icon}</span>
          <span className="rounded-full bg-black/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
            {insight.priority}
          </span>
        </div>
      </div>
      <h3 className="mt-2 text-sm font-semibold text-neutral-100">{insight.title}</h3>
      <p className="mt-1 line-clamp-3 text-xs leading-5 text-neutral-400">{insight.description}</p>
      <div className="mt-2 text-xs text-neutral-500">
        {insight.estimated_audience ? `${insight.estimated_audience} customers` : 'Insight'}
      </div>
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => onAsk(insight.quick_prompt)}
          disabled={disabled}
          className="flex-1 rounded-lg border border-border bg-surface px-2 py-2 text-xs font-medium text-neutral-200 hover:bg-neutral-800 disabled:opacity-60"
        >
          Ask AI
        </button>
        <button
          onClick={() => onQuickLaunch(insight.quick_prompt)}
          disabled={disabled}
          className="flex-1 rounded-lg bg-primary px-2 py-2 text-xs font-medium text-white hover:bg-primary-hover disabled:opacity-60"
        >
          Quick Launch
        </button>
      </div>
    </div>
  )
}
