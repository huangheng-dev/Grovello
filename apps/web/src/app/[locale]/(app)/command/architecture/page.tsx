import { ArchitectureView } from '@/components/architecture-view'
import { setRequestLocale } from 'next-intl/server'

export default async function ArchitecturePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  setRequestLocale(locale)
  return <ArchitectureView />
}
