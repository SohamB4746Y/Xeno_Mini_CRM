import Link from 'next/link'
import clsx from 'clsx'
import type { Campaign } from '@/lib/types'

const statusClass: Record<string, string> = {
  running: 'bg-green-500/10 text-green-300 border-green-500/30',
  completed: 'bg-blue-500/10 text-blue-300 border-blue-500/30',
  draft: 'bg-neutral-500/10 text-neutral-300 border-neutral-500/30',
  paused: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  failed: 'bg-red-500/10 text-red-300 border-red-500/30',
}

const channelClass: Record<string, string> = {
  whatsapp: 'bg-green-500/10 text-green-300',
  email: 'bg-blue-500/10 text-blue-300',
  sms: 'bg-neutral-500/10 text-neutral-300',
  rcs: 'bg-purple-500/10 text-purple-300',
}

type CampaignCardProps = {
  campaign: Campaign
  onLaunch: (campaign: Campaign) => void
}

export function CampaignCard({ campaign, onLaunch }: CampaignCardProps) {
  const analytics = campaign.analytics
  const deliveryRate = Number(analytics?.delivery_rate || 0)

  return (
    <article className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-neutral-100">{campaign.name}</h3>
          <div className="mt-3 flex gap-2">
            <span className={clsx('rounded-full px-2 py-1 text-xs', channelClass[campaign.channel] || channelClass.sms)}>
              {campaign.channel}
            </span>
            <span className={clsx('rounded-full border px-2 py-1 text-xs', statusClass[campaign.status])}>
              {campaign.status}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold">{campaign.total_recipients || 0}</div>
          <div className="text-xs text-neutral-500">recipients</div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg border border-border bg-bg p-3">
          <div className="text-neutral-500">Open Rate</div>
          <div className="mt-1 text-xl font-semibold">{Number(analytics?.open_rate || 0).toFixed(1)}%</div>
        </div>
        <div className="rounded-lg border border-border bg-bg p-3">
          <div className="text-neutral-500">Click Rate</div>
          <div className="mt-1 text-xl font-semibold">{Number(analytics?.click_rate || 0).toFixed(1)}%</div>
        </div>
      </div>

      <div className="mt-5">
        <div className="mb-2 flex justify-between text-xs text-neutral-500">
          <span>Delivery</span>
          <span>{deliveryRate.toFixed(1)}%</span>
        </div>
        <div className="h-2 rounded-full bg-bg">
          <div className="h-2 rounded-full bg-green-500" style={{ width: `${Math.min(deliveryRate, 100)}%` }} />
        </div>
      </div>

      <div className="mt-5 flex gap-3">
        <Link href={`/campaigns/${campaign.id}`} className="flex-1 rounded-lg border border-border px-4 py-2 text-center text-sm text-neutral-200 hover:bg-bg">
          View Details
        </Link>
        {campaign.status === 'draft' && (
          <button onClick={() => onLaunch(campaign)} className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover">
            Launch
          </button>
        )}
      </div>
    </article>
  )
}
