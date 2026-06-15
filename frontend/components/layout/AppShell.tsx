'use client'

import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'
import { CopilotPanel } from '@/components/ai-copilot/CopilotPanel'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'

const titles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/customers': 'Customers',
  '/segments': 'Segments',
  '/campaigns': 'Campaigns',
}

function titleForPath(pathname: string) {
  if (pathname.startsWith('/campaigns/')) return 'Campaign Detail'
  return titles[pathname] || 'Dashboard'
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="flex min-h-screen bg-bg text-neutral-100">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header title={titleForPath(pathname)} />
        <main className="min-h-0 flex-1 overflow-y-auto px-8 py-6">{children}</main>
      </div>
      <CopilotPanel />
    </div>
  )
}
