import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'EuroQuant | Professional Terminal',
  description: 'Institutional European stock market quantitative engine and sentiment analysis.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="it" className="dark h-full">
      <body className="h-full antialiased bg-terminal-bg text-terminal-text selection:bg-terminal-accent selection:text-black">
        {children}
      </body>
    </html>
  )
}
