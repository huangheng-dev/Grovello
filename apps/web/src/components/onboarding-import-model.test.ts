import type {
  BusinessProfile,
  ImportJob,
  WorkspaceOnboarding,
} from '@grovello/api-client'
import { describe, expect, it } from 'vitest'
import {
  canCancelImport,
  canCompensateImport,
  defaultMappings,
  onboardingProgress,
  sourceFieldsFromText,
} from './onboarding-import-model'

const onboarding = {
  requiredObjectTypes: ['brand', 'product', 'market', 'icp'],
} as WorkspaceOnboarding

const profile = {
  objects: [
    { objectType: 'brand', version: { status: 'active' } },
    { objectType: 'product', version: { status: 'draft' } },
    { objectType: 'market', version: { status: 'archived' } },
  ],
} as BusinessProfile

describe('onboarding and import operator model', () => {
  it('computes checklist progress from non-archived canonical facts', () => {
    expect(onboardingProgress(onboarding, profile)).toBe(50)
  })

  it('derives bounded CSV and nested JSON source fields', () => {
    expect(sourceFieldsFromText('slug,name,payload.sku\nalpha,Alpha,A-1', 'csv', ','))
      .toEqual(['slug', 'name', 'payload.sku'])
    expect(sourceFieldsFromText(
      JSON.stringify({ records: [{ slug: 'de', payload: { countryCode: 'DE' } }] }),
      'grovello_json',
      ',',
    )).toEqual(['payload.countryCode', 'slug'])
  })

  it('maps canonical fields directly and other fields into payload', () => {
    expect(defaultMappings(['slug', 'sku'])).toEqual([
      expect.objectContaining({ source: 'slug', target: 'slug', transform: 'trim' }),
      expect.objectContaining({ source: 'sku', target: 'payload.sku' }),
    ])
  })

  it('keeps cancel and compensation actions state-aware', () => {
    expect(canCancelImport({ status: 'validating' } as ImportJob)).toBe(true)
    expect(canCancelImport({ status: 'completed' } as ImportJob)).toBe(false)
    expect(canCompensateImport({ status: 'partially_completed' } as ImportJob)).toBe(true)
  })
})
