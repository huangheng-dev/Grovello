import { JourneysView } from '@/components/journeys-view'
import { setRequestLocale } from 'next-intl/server'

export default async function JourneysPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  setRequestLocale(locale)
  return <JourneysView />
}
