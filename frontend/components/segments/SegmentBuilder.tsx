'use client'

import { useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'

type SegmentBuilderProps = {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

const cities = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune', 'Kolkata', 'Ahmedabad', 'Jaipur', 'Surat']

export function SegmentBuilder({ open, onClose, onCreated }: SegmentBuilderProps) {
  const [tab, setTab] = useState<'manual' | 'ai'>('manual')
  const [name, setName] = useState('New ZURI Segment')
  const [tier, setTier] = useState('gold')
  const [city, setCity] = useState('all')
  const [days, setDays] = useState(60)
  const [minSpend, setMinSpend] = useState(5000)
  const [preview, setPreview] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [aiPrompt, setAiPrompt] = useState('Find customers who bought sarees but have not purchased in 60 days')
  const [error, setError] = useState('')

  const filterRules = useMemo(() => {
    const conditions: Array<Record<string, unknown>> = [
      { field: 'tier', operator: 'eq', value: tier },
      { field: 'last_purchase_at', operator: 'days_ago_gte', value: days },
      { field: 'total_spend', operator: 'gte', value: minSpend },
    ]
    if (city !== 'all') conditions.push({ field: 'city', operator: 'eq', value: city })
    return { operator: 'AND', conditions }
  }, [tier, city, days, minSpend])

  useEffect(() => {
    if (!open || tab !== 'manual') return
    const timer = window.setTimeout(() => {
      api.segments
        .preview(filterRules)
        .then(setPreview)
        .catch((err) => setError(err.message || 'Preview failed'))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [open, tab, filterRules])

  if (!open) return null

  async function saveSegment() {
    setSaving(true)
    setError('')
    try {
      await api.segments.create({
        name,
        description: `${tier} customers${city !== 'all' ? ` in ${city}` : ''} with ₹${minSpend}+ spend and no purchase in ${days}+ days.`,
        filter_rules: filterRules,
        ai_generated: false,
      })
      onCreated()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save segment')
    } finally {
      setSaving(false)
    }
  }

  function askAI() {
    window.dispatchEvent(new CustomEvent('zuri-ai-prompt', { detail: aiPrompt }))
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="w-[680px] rounded-xl border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-lg font-semibold">Create Segment</h2>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-100">Close</button>
        </div>

        <div className="border-b border-border px-5 pt-4">
          <div className="flex gap-2">
            <button
              onClick={() => setTab('manual')}
              className={`rounded-t-lg px-4 py-2 text-sm ${tab === 'manual' ? 'bg-primary text-white' : 'text-neutral-400'}`}
            >
              Build Manually
            </button>
            <button
              onClick={() => setTab('ai')}
              className={`rounded-t-lg px-4 py-2 text-sm ${tab === 'ai' ? 'bg-primary text-white' : 'text-neutral-400'}`}
            >
              Describe to AI
            </button>
          </div>
        </div>

        <div className="space-y-4 px-5 py-5">
          {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

          {tab === 'manual' ? (
            <>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="h-10 w-full rounded-lg border border-border bg-bg px-3 text-sm outline-none"
                placeholder="Segment name"
              />
              <div className="grid grid-cols-4 gap-3">
                <label className="space-y-1 text-xs text-neutral-500">
                  Tier
                  <select value={tier} onChange={(event) => setTier(event.target.value)} className="h-10 w-full rounded-lg border border-border bg-bg px-3 text-sm text-neutral-100">
                    <option value="bronze">Bronze</option>
                    <option value="silver">Silver</option>
                    <option value="gold">Gold</option>
                    <option value="platinum">Platinum</option>
                  </select>
                </label>
                <label className="space-y-1 text-xs text-neutral-500">
                  City
                  <select value={city} onChange={(event) => setCity(event.target.value)} className="h-10 w-full rounded-lg border border-border bg-bg px-3 text-sm text-neutral-100">
                    <option value="all">All cities</option>
                    {cities.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label className="space-y-1 text-xs text-neutral-500">
                  Days since purchase
                  <input type="number" value={days} onChange={(event) => setDays(Number(event.target.value))} className="h-10 w-full rounded-lg border border-border bg-bg px-3 text-sm text-neutral-100" />
                </label>
                <label className="space-y-1 text-xs text-neutral-500">
                  Min spend
                  <input type="number" value={minSpend} onChange={(event) => setMinSpend(Number(event.target.value))} className="h-10 w-full rounded-lg border border-border bg-bg px-3 text-sm text-neutral-100" />
                </label>
              </div>

              <div className="rounded-lg border border-border bg-bg p-4">
                <div className="text-sm font-medium text-neutral-100">
                  This segment will include ~{preview?.customer_count ?? 0} customers
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {(preview?.sample_customers || []).slice(0, 3).map((customer: any) => (
                    <div key={customer.id} className="rounded-lg bg-surface p-3 text-xs">
                      <div className="font-medium text-neutral-100">{customer.name}</div>
                      <div className="mt-1 capitalize text-neutral-500">{customer.tier}</div>
                    </div>
                  ))}
                </div>
              </div>

              <button onClick={saveSegment} disabled={saving} className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-60">
                {saving ? 'Saving...' : 'Save Segment'}
              </button>
            </>
          ) : (
            <>
              <textarea
                value={aiPrompt}
                onChange={(event) => setAiPrompt(event.target.value)}
                rows={7}
                className="w-full rounded-lg border border-border bg-bg p-3 text-sm outline-none"
              />
              <button onClick={askAI} className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-white hover:bg-primary-hover">
                Send to AI Copilot
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
