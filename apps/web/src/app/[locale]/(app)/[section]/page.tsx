import { DomainOverview } from '@/components/domain-overview'
import { findNavigationSection, navigationSections } from '@grovello/product-config'
import { setRequestLocale } from 'next-intl/server'
import { notFound } from 'next/navigation'

export function generateStaticParams() {
  return navigationSections.map((section) => ({ section: section.slug }))
}

export default async function DomainOverviewPage({ params }: { params: Promise<{ locale: string; section: string }> }) {
  const { locale, section: sectionSlug } = await params
  setRequestLocale(locale)
  const section = findNavigationSection(sectionSlug)
  if (!section) notFound()
  return <DomainOverview section={section} />
}
