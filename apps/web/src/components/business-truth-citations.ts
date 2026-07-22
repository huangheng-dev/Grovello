import type { BusinessObject, BusinessTruthCitation, BusinessTruthCitationInput } from '@grovello/api-client'

export type CitationLocatorKind = 'section' | 'page' | 'url' | 'record' | 'custom'

export interface EditableBusinessCitation {
  id: string
  evidenceVersionId: string
  claimText: string
  locatorKind: CitationLocatorKind
  locatorValue: string
}

export class BusinessCitationValidationError extends Error {
  constructor(
    public readonly code: 'citationEvidence' | 'citationClaim' | 'citationLocator' | 'citationLocatorJson',
    public readonly line: number,
  ) {
    super(code)
  }
}

export function emptyBusinessCitation(id: string): EditableBusinessCitation {
  return {
    id,
    evidenceVersionId: '',
    claimText: '',
    locatorKind: 'section',
    locatorValue: '',
  }
}

export function decodeBusinessCitations(
  citations: BusinessTruthCitation[],
  idFactory: () => string,
): EditableBusinessCitation[] {
  return citations.map((citation) => {
    const locator = decodeLocator(citation.locator)
    return {
      id: idFactory(),
      evidenceVersionId: citation.evidenceVersionId,
      claimText: citation.claimText,
      ...locator,
    }
  })
}

export function encodeBusinessCitations(
  citations: EditableBusinessCitation[],
): BusinessTruthCitationInput[] {
  return citations.map((citation, index) => {
    const line = index + 1
    const evidenceVersionId = citation.evidenceVersionId.trim()
    const claimText = citation.claimText.trim()
    const locatorValue = citation.locatorValue.trim()
    if (!evidenceVersionId) throw new BusinessCitationValidationError('citationEvidence', line)
    if (!claimText) throw new BusinessCitationValidationError('citationClaim', line)
    if (!locatorValue) throw new BusinessCitationValidationError('citationLocator', line)
    return {
      evidenceVersionId,
      claimText,
      locator: encodeLocator(citation.locatorKind, locatorValue, line),
    }
  })
}

export function evidenceVersionOptions(objects: BusinessObject[]) {
  return objects.filter(
    (object) => object.objectType === 'evidence' && object.version.status !== 'archived',
  )
}

export function formatCitationLocator(locator: Record<string, unknown>) {
  const decoded = citationLocatorParts(locator)
  return decoded.locatorKind === 'custom'
    ? decoded.locatorValue
    : `${decoded.locatorKind}: ${decoded.locatorValue}`
}

export function citationLocatorParts(locator: Record<string, unknown>) {
  return decodeLocator(locator)
}

function decodeLocator(locator: Record<string, unknown>): Pick<EditableBusinessCitation, 'locatorKind' | 'locatorValue'> {
  const keys = Object.keys(locator)
  if (keys.length === 1) {
    const kind = keys[0]
    const value = kind ? locator[kind] : undefined
    if (kind && isLocatorKind(kind) && (typeof value === 'string' || typeof value === 'number')) {
      return { locatorKind: kind, locatorValue: String(value) }
    }
  }
  return { locatorKind: 'custom', locatorValue: JSON.stringify(locator) }
}

function encodeLocator(kind: CitationLocatorKind, value: string, line: number) {
  if (kind === 'custom') {
    try {
      const locator = JSON.parse(value) as unknown
      if (!locator || Array.isArray(locator) || typeof locator !== 'object') throw new Error('object required')
      return locator as Record<string, unknown>
    } catch {
      throw new BusinessCitationValidationError('citationLocatorJson', line)
    }
  }
  return { [kind]: kind === 'page' && /^\d+$/.test(value) ? Number(value) : value }
}

function isLocatorKind(value: string): value is Exclude<CitationLocatorKind, 'custom'> {
  return value === 'section' || value === 'page' || value === 'url' || value === 'record'
}
