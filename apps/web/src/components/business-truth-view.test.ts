import type { BusinessObject, BusinessProfile } from '@grovello/api-client'
import { describe, expect, it } from 'vitest'
import {
  businessTruthCreateTypesByPage,
  filterBusinessTruthObjects,
  objectsForCapability,
  profileAfterMutation,
  slugifyBusinessObjectName,
} from './business-truth-model'

function object(objectType: BusinessObject['objectType']): BusinessObject {
  return { objectType } as BusinessObject
}

describe('business truth capability mapping', () => {
  it('maps product navigation to products, offers, and price books', () => {
    const objects = [object('brand'), object('product'), object('offer'), object('price_book')]
    expect(objectsForCapability(objects, 'products').map((item) => item.objectType)).toEqual([
      'product',
      'offer',
      'price_book',
    ])
  })

  it('keeps evidence and knowledge records together without including assets', () => {
    const objects = [object('evidence'), object('knowledge_document'), object('case_study'), object('asset')]
    expect(objectsForCapability(objects, 'knowledge').map((item) => item.objectType)).toEqual([
      'evidence',
      'knowledge_document',
      'case_study',
    ])
  })

  it('keeps derived knowledge chunks visible but excludes only derived chunks from owner-created types', () => {
    expect(businessTruthCreateTypesByPage.knowledge).toEqual(['evidence', 'knowledge_document', 'case_study'])
    const objects = [object('knowledge_chunk')]
    expect(objectsForCapability(objects, 'knowledge')).toEqual(objects)
  })

  it('filters loaded knowledge records by type and governed content', () => {
    const evidence = {
      ...object('evidence'),
      slug: 'warranty-evidence',
      version: {
        name: 'Warranty record',
        businessPurpose: 'Support approved product claims',
        payload: { keyFindings: ['24-month fictional warranty'] },
        citations: [],
      },
    } as unknown as BusinessObject
    const knowledge = {
      ...object('knowledge_document'),
      slug: 'installation-guide',
      version: { name: 'Installation guide', businessPurpose: '', payload: {}, citations: [] },
    } as unknown as BusinessObject

    expect(filterBusinessTruthObjects([evidence, knowledge], '24-month', 'all')).toEqual([evidence])
    expect(filterBusinessTruthObjects([evidence, knowledge], '', 'knowledge_document')).toEqual([knowledge])
  })

  it('creates API-safe stable slugs for international Latin names', () => {
    expect(slugifyBusinessObjectName('München Servo Drive — 2026')).toBe('munchen-servo-drive-2026')
  })

  it('applies an authoritative mutation without waiting for a follow-up read', () => {
    const brand = { ...object('brand'), id: 'brand-1', version: { status: 'active', citations: [] } } as unknown as BusinessObject
    const profile = {
      objects: [],
      objectCount: 0,
      citationCount: 0,
      missingObjectTypes: ['brand'],
      validationState: 'incomplete',
      workspaceId: 'workspace-1',
    } as BusinessProfile
    const updated = profileAfterMutation(profile, brand)
    expect(updated.objectCount).toBe(1)
    expect(updated.objects[0]).toBe(brand)
    expect(updated.missingObjectTypes).not.toContain('brand')
  })
})
