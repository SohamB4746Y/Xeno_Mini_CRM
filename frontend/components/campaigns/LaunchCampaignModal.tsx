'use client'

import type { Campaign } from '@/lib/types'

type LaunchCampaignModalProps = {
  campaign: Campaign | null
  onClose: () => void
  onConfirm: () => void
  loading?: boolean
}

export function LaunchCampaignModal({ campaign, onClose, onConfirm, loading }: LaunchCampaignModalProps) {
  if (!campaign) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="w-[520px] rounded-xl border border-border bg-surface p-5 shadow-2xl">
        <h2 className="text-lg font-semibold">Launch Campaign</h2>
        <p className="mt-2 text-sm text-neutral-400">
          This will dispatch {campaign.name} to its selected segment through {campaign.channel}.
        </p>
        <div className="mt-4 rounded-lg border border-border bg-bg p-4 text-sm">
          <div className="flex justify-between">
            <span className="text-neutral-500">Recipients</span>
            <span>{campaign.total_recipients || 'Calculated on launch'}</span>
          </div>
          <div className="mt-2 flex justify-between">
            <span className="text-neutral-500">Status</span>
            <span>{campaign.status}</span>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-3">
          <button onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm text-neutral-300 hover:bg-bg">
            Cancel
          </button>
          <button onClick={onConfirm} disabled={loading} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-60">
            {loading ? 'Launching...' : 'Launch now'}
          </button>
        </div>
      </div>
    </div>
  )
}
