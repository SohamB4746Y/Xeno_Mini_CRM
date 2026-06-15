import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ZURI CRM',
  description: 'AI-native mini CRM for ZURI',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
