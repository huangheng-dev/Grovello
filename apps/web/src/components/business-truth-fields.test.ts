import type { BusinessObject } from '@grovello/api-client'
import { describe, expect, it } from 'vitest'
import {
  BusinessFieldValidationError,
  decodeStructuredPayload,
  encodeStructuredPayload,
  referencedObjects,
} from './business-truth-fields'

describe('structured business truth fields', () => {
  it('round-trips governed brand fields while retaining unknown legacy attributes', () => {
    const decoded = decodeStructuredPayload('brand', {
      industry: 'Industrial automation',
      voiceTraits: ['precise', 'practical'],
      legacyTaxonomy: { level: 2 },
    })

    expect(decoded.fields.voiceTraits).toBe('precise\npractical')
    expect(decoded.preserved).toEqual({ legacyTaxonomy: { level: 2 } })
    expect(encodeStructuredPayload('brand', decoded.fields, decoded.preserved)).toEqual({
      industry: 'Industrial automation',
      voiceTraits: ['precise', 'practical'],
      legacyTaxonomy: { level: 2 },
    })
  })

  it('turns price-book rows into typed amounts and normalizes currency', () => {
    expect(encodeStructuredPayload('price_book', {
      currency: 'eur',
      market: 'Germany',
      priceBasis: 'list',
      validFrom: '2026-08-01',
      validTo: '2026-12-31',
      priceEntries: 'x200-standard | 12500.50 | one-time',
    }, {})).toMatchObject({
      currency: 'EUR',
      priceEntries: [{ itemReference: 'x200-standard', amount: 12500.5, unit: 'one-time' }],
    })
  })

  it('rejects an inverted price-book validity period', () => {
    expect(() => encodeStructuredPayload('price_book', {
      currency: 'EUR',
      validFrom: '2026-12-31',
      validTo: '2026-01-01',
    }, {})).toThrowError(BusinessFieldValidationError)
  })

  it('only offers non-archived canonical products as offer references', () => {
    const objects = [
      { id: 'product-active', objectType: 'product', version: { status: 'active' } },
      { id: 'product-archived', objectType: 'product', version: { status: 'archived' } },
      { id: 'brand-active', objectType: 'brand', version: { status: 'active' } },
    ] as BusinessObject[]
    expect(referencedObjects(objects, ['product']).map((object) => object.id)).toEqual(['product-active'])
  })

  it('normalizes canonical market codes and list attributes', () => {
    expect(encodeStructuredPayload('market', {
      countryCode: 'de',
      languages: 'de\nen',
      currency: 'eur',
      marketStatus: 'prioritized',
      priority: 'tier_1',
      entryMode: 'direct_sales',
    }, {})).toMatchObject({
      countryCode: 'DE',
      languages: ['de', 'en'],
      currency: 'EUR',
    })
  })

  it('rejects invalid market country codes', () => {
    expect(() => encodeStructuredPayload('market', { countryCode: 'Germany' }, {}))
      .toThrowError(BusinessFieldValidationError)
  })

  it('stores buying committee rows as structured ICP members', () => {
    const payload = encodeStructuredPayload('icp', {
      marketId: 'market-id',
      industry: 'Industrial machinery',
      companySize: 'mid_market',
      pains: 'Unplanned downtime',
      triggers: 'Factory modernization',
      buyingCommittee: 'Plant manager | high influence | uptime and implementation risk',
      qualificationCriteria: 'Operates automated production lines',
      exclusions: 'No local service capacity',
    }, {})
    expect(payload.buyingCommittee).toEqual([{
      role: 'Plant manager',
      influence: 'high influence',
      priorities: 'uptime and implementation risk',
    }])
    expect(decodeStructuredPayload('icp', payload).fields.buyingCommittee)
      .toBe('Plant manager | high influence | uptime and implementation risk')
  })

  it('structures evidence provenance, verification, findings, and limitations', () => {
    const payload = encodeStructuredPayload('evidence', {
      evidenceType: 'technical_record',
      sourceTitle: 'X200 fictional qualification record',
      collectedAt: '2026-07-21',
      sourceLocale: 'en',
      verificationStatus: 'owner_attested',
      reliability: 'medium',
      usageRights: 'owner_provided',
      scope: 'Fictional German machine-builder acceptance fixture',
      evidenceSummary: 'A fictional record used only to verify the evidence workflow.',
      keyFindings: 'The acceptance fixture records a 24-month warranty.',
      limitations: 'Not a real product claim.\nNot for external publication.',
    }, {})

    expect(payload).toMatchObject({
      verificationStatus: 'owner_attested',
      keyFindings: ['The acceptance fixture records a 24-month warranty.'],
      limitations: ['Not a real product claim.', 'Not for external publication.'],
    })
  })

  it('links a knowledge document to one canonical subject and stores retrieval terms', () => {
    const payload = encodeStructuredPayload('knowledge_document', {
      documentType: 'product_guide',
      canonicalObjectId: 'product-1',
      sourceLocale: 'en',
      ownerTeam: 'Product operations',
      knowledgeStatus: 'approved',
      documentSummary: 'Governed fictional product overview.',
      knowledgeBody: 'This content is fictional and exists for workflow acceptance only.',
      topics: 'servo drive\nindustrial automation',
      retrievalKeywords: 'X200\nservo modernization',
    }, {})

    expect(payload).toMatchObject({
      canonicalObjectId: 'product-1',
      topics: ['servo drive', 'industrial automation'],
      retrievalKeywords: ['X200', 'servo modernization'],
    })
  })

  it('structures a governed case study without flattening measured outcomes', () => {
    const payload = encodeStructuredPayload('case_study', {
      caseStudyType: 'pilot',
      disclosureStatus: 'fictional_fixture',
      customerDisplayName: 'Alpine Robotics（虚构）',
      customerIndustry: 'Industrial automation',
      marketId: 'market-1',
      productId: 'product-1',
      engagementStartedAt: '2026-01-15',
      engagementEndedAt: '2026-04-15',
      caseSummary: 'A governed fictional acceptance case.',
      challenge: 'Validate the case-study workflow.',
      approach: 'Pin structured outcomes to evidence.',
      outcomes: 'Acceptance coverage | One governed workflow | 2026 fixture | Fictional evidence record',
      lessons: 'Keep measured outcomes separate from marketing claims.',
      limitations: 'Not a real customer result.',
      approvedUseCases: 'Product workflow acceptance',
      authorizationReference: 'fictional-fixture',
      ownerTeam: 'Product operations',
    }, {})

    expect(payload.outcomes).toEqual([{
      metric: 'Acceptance coverage',
      result: 'One governed workflow',
      period: '2026 fixture',
      evidenceNote: 'Fictional evidence record',
    }])
    expect(decodeStructuredPayload('case_study', payload).fields.outcomes)
      .toBe('Acceptance coverage | One governed workflow | 2026 fixture | Fictional evidence record')
  })

  it('rejects a case-study end date before its engagement start', () => {
    expect(() => encodeStructuredPayload('case_study', {
      engagementStartedAt: '2026-04-15',
      engagementEndedAt: '2026-01-15',
    }, {})).toThrowError(BusinessFieldValidationError)
  })
})
