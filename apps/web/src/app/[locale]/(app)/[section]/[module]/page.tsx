import { BusinessTruthView } from '@/components/business-truth-view'
import { AssetLibraryView } from '@/components/asset-library-view'
import { ModuleView } from '@/components/module-view'
import { findNavigationItem, isNavigationItemRoutable, navigationItems } from '@grovello/product-config'
import { setRequestLocale } from 'next-intl/server'
import { notFound } from 'next/navigation'

export function generateStaticParams() {
  return navigationItems
    .filter((item) => isNavigationItemRoutable(item) && !(item.sectionSlug === 'command' && ['dashboard', 'journeys', 'architecture'].includes(item.slug)))
    .map((item) => ({ section: item.sectionSlug, module: item.slug }))
}

export default async function CapabilityPage({ params }: { params: Promise<{ locale: string; section: string; module: string }> }) {
  const { locale, section, module } = await params
  setRequestLocale(locale)
  const item = findNavigationItem(section, module)
  if (!item || !isNavigationItemRoutable(item)) notFound()
  if (item.key === 'assets') return <AssetLibraryView item={item} />
  if (item.sectionKey === 'brand') return <BusinessTruthView item={item} />
  return <ModuleView item={item} />
}
