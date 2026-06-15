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

function formatDate(value: string | null) {
  if (!value) return 'Not launched'
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short' }).format(new Date(value))
}

export function RecentCampaigns({ campaigns }: { campaigns: Campaign[] }) {
  return (
    <section className="rounded-xl border border-border bg-surface">
      <div className="border-b border-border px-5 py-4">
        <h2 className="font-semibold text-neutral-100">Recent Campaigns</h2>
      </div>
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-neutral-500">
          <tr>
            <th className="px-5 py-3 font-medium">Name</th>
            <th className="px-5 py-3 font-medium">Channel</th>
            <th className="px-5 py-3 font-medium">Status</th>
            <th className="px-5 py-3 font-medium">Recipients</th>
            <th className="px-5 py-3 font-medium">Open Rate</th>
            <th className="px-5 py-3 font-medium">Launched</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {campaigns.map((campaign) => (
            <tr key={campaign.id} className="text-neutral-300">
              <td className="px-5 py-4 font-medium text-neutral-100">{campaign.name}</td>
              <td className="px-5 py-4">
                <span className={clsx('rounded-full px-2 py-1 text-xs', channelClass[campaign.channel] || channelClass.sms)}>
                  {campaign.channel}
                </span>
              </td>
              <td className="px-5 py-4">
                <span className={clsx('rounded-full border px-2 py-1 text-xs', statusClass[campaign.status])}>
                  {campaign.status}
                </span>
              </td>
              <td className="px-5 py-4">{campaign.total_recipients?.toLocaleString() || 0}</td>
              <td className="px-5 py-4">{Number(campaign.analytics?.open_rate || 0).toFixed(1)}%</td>
              <td className="px-5 py-4 text-neutral-500">{formatDate(campaign.launched_at)}</td>
            </tr>
          ))}
          {!campaigns.length && (
            <tr>
              <td colSpan={6} className="px-5 py-10 text-center text-neutral-500">
                No campaigns yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  )
}
