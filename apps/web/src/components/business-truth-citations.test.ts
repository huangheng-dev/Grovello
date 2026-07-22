import type { BusinessObject, BusinessTruthCitation } from '@grovello/api-client'
import { describe, expect, it } from 'vitest'
import {
  BusinessCitationValidationError,
  decodeBusinessCitations,
  encodeBusinessCitations,
  evidenceVersionOptions,
  formatCitationLocator,
} from './business-truth-citations'

describe('business truth citations', () => {
  it('round-trips an exact evidence version and structured page locator', () => {
    const decoded = decodeBusinessCitations([{
      id: 'citation-1',
      evidenceObjectId: 'evidence-1',
      evidenceVersionId: 'evidence-version-2',
      evidenceVersion: 2,
      evidenceName: 'Warranty record',
      claimText: 'The fictional product has a 24-month warranty.',
      locator: { page: 4 },
    }], () => 'editor-1')

    expect(decoded[0]).toMatchObject({
      evidenceVersionId: 'evidence-version-2',
      locatorKind: 'page',
      locatorValue: '4',
    })
    expect(encodeBusinessCitations(decoded)[0]).toEqual({
      evidenceVersionId: 'evidence-version-2',
      claimText: 'The fictional product has a 24-month warranty.',
      locator: { page: 4 },
    })
  })

  it('preserves a legacy compound locator through the custom JSON path', () => {
    const citation = {
      id: 'citation-1',
      evidenceObjectId: 'evidence-1',
      evidenceVersionId: 'version-1',
      evidenceVersion: 1,
      evidenceName: 'Evidence',
      claimText: 'Supported claim',
      locator: { section: 'terms', paragraph: 2 },
    } satisfies BusinessTruthCitation
    const decoded = decodeBusinessCitations([citation], () => 'editor-1')
    expect(decoded[0]!.locatorKind).toBe('custom')
    expect(encodeBusinessCitations(decoded)[0]!.locator).toEqual({ section: 'terms', paragraph: 2 })
  })

  it('rejects an incomplete citation row', () => {
    expect(() => encodeBusinessCitations([{
      id: 'editor-1',
      evidenceVersionId: '',
      claimText: 'Claim',
      locatorKind: 'section',
      locatorValue: 'summary',
    }])).toThrowError(BusinessCitationValidationError)
  })

  it('offers only current non-archived evidence versions', () => {
    const objects = [
      { id: 'evidence-live', objectType: 'evidence', version: { status: 'active' } },
      { id: 'evidence-old', objectType: 'evidence', version: { status: 'archived' } },
      { id: 'product', objectType: 'product', version: { status: 'active' } },
    ] as BusinessObject[]
    expect(evidenceVersionOptions(objects).map((object) => object.id)).toEqual(['evidence-live'])
  })

  it('formats common locators without exposing JSON syntax', () => {
    expect(formatCitationLocator({ section: 'technical-data' })).toBe('section: technical-data')
  })
})
