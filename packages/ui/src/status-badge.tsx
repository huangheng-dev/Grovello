import type { ReactNode } from 'react'

export type BadgeTone = 'positive' | 'warning' | 'neutral' | 'info' | 'critical'

export function StatusBadge({ children, tone = 'neutral' }: { children: ReactNode; tone?: BadgeTone }) {
  return <span className={`status-badge status-badge--${tone}`}>{children}</span>
}
