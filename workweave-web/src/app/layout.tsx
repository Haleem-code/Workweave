import type { Metadata, Viewport } from 'next'
import '../workspace.css'

export const metadata: Metadata = {
  title: 'Workweave: Company knowledge, connected',
  description: 'Connect company knowledge to commitments, responsible teams, and accountable work.'
}

export const viewport: Viewport = {
  themeColor: '#f7f6f2',
  width: 'device-width',
  initialScale: 1
}

export default function RootLayout({
  children
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>

      <body>{children}</body>
    </html>
  )
}
