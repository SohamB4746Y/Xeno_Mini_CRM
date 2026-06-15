import type { Segment } from '@/lib/types'

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value))
}

export function SegmentCard({ segment }: { segment: Segment }) {
  return (
    <article className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-neutral-100">{segment.name}</h3>
          <p className="mt-2 min-h-10 text-sm leading-5 text-neutral-500">{segment.description || 'No description provided.'}</p>
        </div>
        {segment.ai_generated && (
          <span className="shrink-0 rounded-full bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
            AI Generated
          </span>
        )}
      </div>
      <div className="mt-5 flex items-end justify-between">
        <div>
          <div className="text-3xl font-semibold text-neutral-100">{segment.customer_count.toLocaleString()}</div>
          <div className="text-xs text-neutral-500">customers</div>
        </div>
        <div className="text-xs text-neutral-500">{formatDate(segment.created_at)}</div>
      </div>
    </article>
  )
}
