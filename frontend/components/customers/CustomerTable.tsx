'use client'

import clsx from 'clsx'
import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import type { Customer, CustomerListResponse } from '@/lib/types'

const tierClass = {
  platinum: 'bg-purple-500/10 text-purple-300 border-purple-500/30',
  gold: 'bg-yellow-500/10 text-yellow-300 border-yellow-500/30',
  silver: 'bg-neutral-500/10 text-neutral-300 border-neutral-500/30',
  bronze: 'bg-orange-500/10 text-orange-300 border-orange-500/30',
}

const channelIcon: Record<string, string> = {
  whatsapp: '📱',
  email: '📧',
  sms: '💬',
  rcs: '🔵',
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(value || 0))
}

function lastPurchase(customer: Customer) {
  if (customer.days_since_purchase == null) return 'No purchase'
  if (customer.days_since_purchase === 0) return 'Today'
  return `${customer.days_since_purchase} days ago`
}

export function CustomerTable() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [tier, setTier] = useState('all')
  const [city, setCity] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const pageSize = 20

  const cities = useMemo(() => {
    const known = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune', 'Kolkata', 'Ahmedabad', 'Jaipur', 'Surat']
    return known
  }, [])

  useEffect(() => {
    setLoading(true)
    api.customers
      .list({ page, page_size: pageSize, search, tier, city })
      .then((data) => {
        const response = data as CustomerListResponse
        setCustomers(response.items || [])
        setTotal(response.total || 0)
        setError('')
      })
      .catch((err) => setError(err.message || 'Could not load customers'))
      .finally(() => setLoading(false))
  }, [page, search, tier, city])

  const totalPages = Math.max(Math.ceil(total / pageSize), 1)

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-neutral-100">{total.toLocaleString()} customers</h2>
          <p className="text-sm text-neutral-500">Search, filter, and inspect ZURI shoppers.</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
            <input
              value={search}
              onChange={(event) => {
                setPage(1)
                setSearch(event.target.value)
              }}
              placeholder="Search name or email"
              className="h-10 w-64 rounded-lg border border-border bg-surface pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
          <select
            value={tier}
            onChange={(event) => {
              setPage(1)
              setTier(event.target.value)
            }}
            className="h-10 rounded-lg border border-border bg-surface px-3 text-sm outline-none"
          >
            <option value="all">All tiers</option>
            <option value="bronze">Bronze</option>
            <option value="silver">Silver</option>
            <option value="gold">Gold</option>
            <option value="platinum">Platinum</option>
          </select>
          <select
            value={city}
            onChange={(event) => {
              setPage(1)
              setCity(event.target.value)
            }}
            className="h-10 rounded-lg border border-border bg-surface px-3 text-sm outline-none"
          >
            <option value="all">All cities</option>
            {cities.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      <div className="overflow-hidden rounded-xl border border-border bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-5 py-3 font-medium">Name</th>
              <th className="px-5 py-3 font-medium">Email</th>
              <th className="px-5 py-3 font-medium">City</th>
              <th className="px-5 py-3 font-medium">Tier</th>
              <th className="px-5 py-3 font-medium">Total Spend</th>
              <th className="px-5 py-3 font-medium">Orders</th>
              <th className="px-5 py-3 font-medium">Last Purchase</th>
              <th className="px-5 py-3 font-medium">Channel</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading
              ? [0, 1, 2, 3, 4].map((item) => (
                  <tr key={item}>
                    <td colSpan={8} className="px-5 py-4">
                      <div className="h-5 animate-pulse rounded bg-neutral-800" />
                    </td>
                  </tr>
                ))
              : customers.map((customer) => (
                  <tr key={customer.id} className="text-neutral-300">
                    <td className="px-5 py-4 font-medium text-neutral-100">{customer.name}</td>
                    <td className="px-5 py-4 text-neutral-400">{customer.email}</td>
                    <td className="px-5 py-4">{customer.city}</td>
                    <td className="px-5 py-4">
                      <span className={clsx('rounded-full border px-2 py-1 text-xs capitalize', tierClass[customer.tier])}>
                        {customer.tier}
                      </span>
                    </td>
                    <td className="px-5 py-4">{formatCurrency(customer.total_spend)}</td>
                    <td className="px-5 py-4">{customer.total_orders}</td>
                    <td className="px-5 py-4 text-neutral-500">{lastPurchase(customer)}</td>
                    <td className="px-5 py-4">
                      {channelIcon[customer.preferred_channel]} {customer.preferred_channel}
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-neutral-400">
        <button
          onClick={() => setPage((value) => Math.max(value - 1, 1))}
          disabled={page === 1}
          className="rounded-lg border border-border px-4 py-2 hover:bg-surface disabled:opacity-40"
        >
          Prev
        </button>
        <span>
          Page {page} of {totalPages}
        </span>
        <button
          onClick={() => setPage((value) => Math.min(value + 1, totalPages))}
          disabled={page >= totalPages}
          className="rounded-lg border border-border px-4 py-2 hover:bg-surface disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </section>
  )
}
