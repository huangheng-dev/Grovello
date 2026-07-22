import { DeliveryRoadmapView } from '@/components/delivery-roadmap-view'
import { setRequestLocale } from 'next-intl/server'

export default async function DeliveryRoadmapPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  setRequestLocale(locale)
  return <DeliveryRoadmapView />
}
