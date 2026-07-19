import { describe, expect, it } from 'vitest'
import { navigationItems, navigationSections } from './navigation'

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
})
