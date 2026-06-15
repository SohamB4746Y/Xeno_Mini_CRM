'use client'

import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { SegmentBuilder } from '@/components/segments/SegmentBuilder'
import { SegmentCard } from '@/components/segments/SegmentCard'
import { api } from '@/lib/api'
import type { Segment, SegmentListResponse } from '@/lib/types'

export default function SegmentsPage() {
  const [segments, setSegments] = useState<Segment[]>([])
  const [builderOpen, setBuilderOpen] = useState(false)
  const [selectedSegment, setSelectedSegment] = useState('')
  const [channel, setChannel] = useState('whatsapp')
  const [message, setMessage] = useState('Hi {{name}}, we miss you at ZURI. Your {{tier}} edit is ready with styles inspired by {{last_product}}.')
  const [campaignName, setCampaignName] = useState('AI-assisted ZURI Campaign')
  const [error, setError] = useState('')
  const [createdCampaignId, setCreatedCampaignId] = useState('')

  function loadSegments() {
    api.segments
      .list()
      .then((data) => {
        const response = data as SegmentListResponse
        setSegments(response.items || [])
        if (!selectedSegment && response.items?.[0]) setSelectedSegment(response.items[0].id)
      })
      .catch((err) => setError(err.message || 'Could not load segments'))
  }

  useEffect(() => {
    loadSegments()
  }, [])

  async function createCampaign() {
    if (!selectedSegment) return
    setError('')
    try {
      const campaign: any = await api.campaigns.create({
        name: campaignName,
        segment_id: selectedSegment,
        channel,
        message_template: message,
      })
      setCreatedCampaignId(campaign.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create campaign')
    }
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Audience Segments</h2>
            <p className="text-sm text-neutral-500">Saved audiences ready for AI-assisted campaign execution.</p>
          </div>
          <button onClick={() => setBuilderOpen(true)} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover">
            Create Segment
          </button>
        </div>

        {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

        <div className="grid grid-cols-2 gap-4">
          {segments.map((segment) => <SegmentCard key={segment.id} segment={segment} />)}
        </div>

        <section className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-lg font-semibold">New Campaign</h2>
          <p className="mt-1 text-sm text-neutral-500">Create a draft campaign from any saved segment.</p>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <input value={campaignName} onChange={(event) => setCampaignName(event.target.value)} className="h-10 rounded-lg border border-border bg-bg px-3 text-sm outline-none" />
            <select value={selectedSegment} onChange={(event) => setSelectedSegment(event.target.value)} className="h-10 rounded-lg border border-border bg-bg px-3 text-sm outline-none">
              {segments.map((segment) => <option key={segment.id} value={segment.id}>{segment.name}</option>)}
            </select>
            <select value={channel} onChange={(event) => setChannel(event.target.value)} className="h-10 rounded-lg border border-border bg-bg px-3 text-sm outline-none">
              <option value="whatsapp">WhatsApp</option>
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="rcs">RCS</option>
            </select>
            <div className="rounded-lg border border-border bg-bg px-3 py-2 text-xs text-neutral-500">
              Tokens: {'{{name}}'} {'{{city}}'} {'{{tier}}'} {'{{last_product}}'} {'{{days_since_purchase}}'}
            </div>
          </div>
          <textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={4} className="mt-4 w-full rounded-lg border border-border bg-bg p-3 text-sm outline-none" />
          <div className="mt-4 rounded-lg border border-border bg-bg p-3 text-sm text-neutral-300">
            Preview: {message.replace('{{name}}', 'Priya').replace('{{tier}}', 'Gold').replace('{{last_product}}', 'Silk Saree').replace('{{city}}', 'Mumbai').replace('{{days_since_purchase}}', '74')}
          </div>
          <button onClick={createCampaign} className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover">
            Create Campaign
          </button>
          {createdCampaignId && (
            <a href={`/campaigns/${createdCampaignId}`} className="ml-4 text-sm text-primary hover:underline">
              Open campaign
            </a>
          )}
        </section>
      </div>
      <SegmentBuilder open={builderOpen} onClose={() => setBuilderOpen(false)} onCreated={loadSegments} />
    </AppShell>
  )
}
