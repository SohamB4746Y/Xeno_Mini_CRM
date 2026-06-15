'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { BarChart3, Filter, LayoutDashboard, Send, Users } from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/customers', label: 'Customers', icon: Users },
  { href: '/segments', label: 'Segments', icon: Filter },
  { href: '/campaigns', label: 'Campaigns', icon: Send },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-border bg-bg px-4 py-5">
      <div className="mb-8">
        <div className="text-2xl font-bold tracking-wide text-primary">ZURI</div>
        <div className="text-xs font-medium uppercase tracking-[0.24em] text-neutral-500">CRM</div>
      </div>

      <nav className="space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition',
                active
                  ? 'bg-primary text-white shadow-lg shadow-primary/20'
                  : 'text-neutral-400 hover:bg-surface hover:text-neutral-100',
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="mt-auto rounded-lg border border-primary/30 bg-primary/10 px-3 py-3 text-xs text-neutral-300">
        <div className="font-semibold text-primary">Powered by AI</div>
        <div className="mt-1 text-neutral-500">Marketing intelligence always on.</div>
      </div>
    </aside>
  )
}
