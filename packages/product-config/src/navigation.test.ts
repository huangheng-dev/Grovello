import { describe, expect, it } from 'vitest'
import { getPrimaryNavigationItems, navigationItems, navigationSections } from './navigation'

describe('Grovello navigation', () => {
  it('preserves ten fixed product domains', () => expect(navigationSections).toHaveLength(10))
  it('uses unique routes', () => {
    const routes = navigationItems.map((item) => `${item.sectionSlug}/${item.slug}`)
    expect(new Set(routes).size).toBe(routes.length)
  })
  it('keeps SEO and GEO separate', () => {
    expect(navigationItems.some((item) => item.key === 'seo')).toBe(true)
    expect(navigationItems.some((item) => item.key === 'geo')).toBe(true)
  })
  it('exposes the delivery roadmap as a real Growth Command capability', () => {
    expect(navigationItems).toContainEqual(expect.objectContaining({ key: 'deliveryRoadmap', status: 'active' }))
  })
  it('keeps reserved capabilities out of primary navigation', () => {
    const visibleItems = navigationSections.flatMap(getPrimaryNavigationItems)
    expect(visibleItems.every((item) => item.status !== 'reserved')).toBe(true)
    expect(navigationItems.some((item) => item.status === 'reserved')).toBe(true)
  })
  it('declares delivery and audience metadata for every capability', () => {
    expect(navigationItems.every((item) => item.phase > 0)).toBe(true)
    expect(navigationItems.every((item) => ['operator', 'admin', 'developer'].includes(item.audience))).toBe(true)
  })
})
