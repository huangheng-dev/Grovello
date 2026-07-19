import { DashboardView } from '@/components/dashboard-view'
import { setRequestLocale } from 'next-intl/server'

export default async function DashboardPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  setRequestLocale(locale)
  return <DashboardView />
}
