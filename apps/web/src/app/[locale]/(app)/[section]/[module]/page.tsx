import { ModuleView } from '@/components/module-view'
import { findNavigationItem, navigationItems } from '@grovello/product-config'
import { setRequestLocale } from 'next-intl/server'
import { notFound } from 'next/navigation'

export function generateStaticParams() {
  return navigationItems
    .filter((item) => !(item.sectionSlug === 'command' && ['dashboard', 'architecture'].includes(item.slug)))
    .map((item) => ({ section: item.sectionSlug, module: item.slug }))
}

export default async function CapabilityPage({ params }: { params: Promise<{ locale: string; section: string; module: string }> }) {
  const { locale, section, module } = await params
  setRequestLocale(locale)
  const item = findNavigationItem(section, module)
  if (!item) notFound()
  return <ModuleView item={item} />
}
