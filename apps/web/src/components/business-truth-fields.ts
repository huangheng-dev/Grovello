import type { BusinessObject, BusinessObjectType } from '@grovello/api-client'

export type BusinessFieldKind = 'text' | 'url' | 'textarea' | 'list' | 'select' | 'date' | 'reference' | 'priceRows' | 'committeeRows' | 'outcomeRows'

export interface BusinessFieldDefinition {
  key: string
  kind: BusinessFieldKind
  required?: boolean
  options?: string[]
  referenceTypes?: BusinessObjectType[]
  span?: 'full'
}

export class BusinessFieldValidationError extends Error {
  constructor(public readonly code: 'currency' | 'countryCode' | 'dateOrder' | 'engagementDateOrder' | 'priceRow' | 'priceAmount' | 'committeeRow' | 'outcomeRow', public readonly line?: number) {
    super(code)
  }
}

export const structuredBusinessFields: Partial<Record<BusinessObjectType, BusinessFieldDefinition[]>> = {
  brand: [
    { key: 'industry', kind: 'text', required: true },
    { key: 'website', kind: 'url' },
    { key: 'positioning', kind: 'textarea', required: true, span: 'full' },
    { key: 'mission', kind: 'textarea', span: 'full' },
    { key: 'primaryAudience', kind: 'textarea', required: true, span: 'full' },
    { key: 'voiceTraits', kind: 'list' },
    { key: 'valuePropositions', kind: 'list' },
  ],
  product: [
    { key: 'category', kind: 'text', required: true },
    { key: 'lifecycleStage', kind: 'select', required: true, options: ['development', 'active', 'retired'] },
    { key: 'summary', kind: 'textarea', required: true, span: 'full' },
    { key: 'targetCustomers', kind: 'list' },
    { key: 'coreCapabilities', kind: 'list' },
    { key: 'differentiators', kind: 'list', span: 'full' },
  ],
  offer: [
    { key: 'productId', kind: 'reference', required: true, referenceTypes: ['product'] },
    { key: 'targetMarket', kind: 'text', required: true },
    { key: 'summary', kind: 'textarea', required: true, span: 'full' },
    { key: 'commercialModel', kind: 'select', required: true, options: ['one_time', 'subscription', 'usage_based', 'custom'] },
    { key: 'availability', kind: 'select', required: true, options: ['planned', 'available', 'paused', 'retired'] },
    { key: 'deliverables', kind: 'list', required: true, span: 'full' },
  ],
  price_book: [
    { key: 'currency', kind: 'text', required: true },
    { key: 'market', kind: 'text', required: true },
    { key: 'priceBasis', kind: 'select', required: true, options: ['list', 'floor', 'partner', 'custom'] },
    { key: 'offerId', kind: 'reference', referenceTypes: ['offer'] },
    { key: 'validFrom', kind: 'date', required: true },
    { key: 'validTo', kind: 'date' },
    { key: 'priceEntries', kind: 'priceRows', required: true, span: 'full' },
  ],
  market: [
    { key: 'countryCode', kind: 'text', required: true },
    { key: 'region', kind: 'text' },
    { key: 'languages', kind: 'list', required: true },
    { key: 'currency', kind: 'text', required: true },
    { key: 'marketStatus', kind: 'select', required: true, options: ['research', 'prioritized', 'active', 'paused'] },
    { key: 'priority', kind: 'select', required: true, options: ['tier_1', 'tier_2', 'watchlist'] },
    { key: 'entryMode', kind: 'select', required: true, options: ['direct_sales', 'partner_led', 'distributor_led', 'digital_self_serve', 'custom'] },
    { key: 'channelAvailability', kind: 'list' },
    { key: 'localizationRequirements', kind: 'list', span: 'full' },
    { key: 'regulatoryNotes', kind: 'textarea', span: 'full' },
    { key: 'assumptions', kind: 'list', span: 'full' },
  ],
  icp: [
    { key: 'marketId', kind: 'reference', required: true, referenceTypes: ['market'] },
    { key: 'productId', kind: 'reference', referenceTypes: ['product'] },
    { key: 'industry', kind: 'text', required: true },
    { key: 'companySize', kind: 'select', required: true, options: ['startup', 'smb', 'mid_market', 'enterprise'] },
    { key: 'employeeRange', kind: 'text' },
    { key: 'revenueRange', kind: 'text' },
    { key: 'targetAccounts', kind: 'list', span: 'full' },
    { key: 'pains', kind: 'list', required: true },
    { key: 'triggers', kind: 'list', required: true },
    { key: 'useCases', kind: 'list', span: 'full' },
    { key: 'buyingCommittee', kind: 'committeeRows', required: true, span: 'full' },
    { key: 'qualificationCriteria', kind: 'list', required: true },
    { key: 'exclusions', kind: 'list', required: true },
  ],
  evidence: [
    { key: 'evidenceType', kind: 'select', required: true, options: ['technical_record', 'market_research', 'customer_interview', 'analytics_snapshot', 'legal_document', 'case_result', 'third_party_report', 'other'] },
    { key: 'sourceTitle', kind: 'text', required: true },
    { key: 'sourceUrl', kind: 'url' },
    { key: 'publisher', kind: 'text' },
    { key: 'publishedAt', kind: 'date' },
    { key: 'collectedAt', kind: 'date', required: true },
    { key: 'sourceLocale', kind: 'text', required: true },
    { key: 'verificationStatus', kind: 'select', required: true, options: ['verified', 'owner_attested', 'third_party', 'unverified'] },
    { key: 'reliability', kind: 'select', required: true, options: ['high', 'medium', 'low'] },
    { key: 'usageRights', kind: 'select', required: true, options: ['owner_provided', 'public_reference', 'licensed', 'internal_only'] },
    { key: 'scope', kind: 'textarea', required: true, span: 'full' },
    { key: 'evidenceSummary', kind: 'textarea', required: true, span: 'full' },
    { key: 'keyFindings', kind: 'list', required: true, span: 'full' },
    { key: 'limitations', kind: 'list', span: 'full' },
    { key: 'reviewAt', kind: 'date' },
  ],
  knowledge_document: [
    { key: 'documentType', kind: 'select', required: true, options: ['product_guide', 'faq', 'policy', 'playbook', 'research_note', 'technical_document', 'training_material', 'other'] },
    { key: 'canonicalObjectId', kind: 'reference', referenceTypes: ['brand', 'product', 'offer', 'market', 'icp'] },
    { key: 'sourceUrl', kind: 'url' },
    { key: 'sourceLocale', kind: 'text', required: true },
    { key: 'ownerTeam', kind: 'text', required: true },
    { key: 'knowledgeStatus', kind: 'select', required: true, options: ['working', 'approved', 'superseded'] },
    { key: 'reviewAt', kind: 'date' },
    { key: 'documentSummary', kind: 'textarea', required: true, span: 'full' },
    { key: 'knowledgeBody', kind: 'textarea', required: true, span: 'full' },
    { key: 'topics', kind: 'list', required: true },
    { key: 'retrievalKeywords', kind: 'list', required: true },
    { key: 'audiences', kind: 'list', span: 'full' },
  ],
  case_study: [
    { key: 'caseStudyType', kind: 'select', required: true, options: ['implementation', 'customer_outcome', 'pilot', 'transformation', 'partner_story', 'internal_validation'] },
    { key: 'disclosureStatus', kind: 'select', required: true, options: ['public', 'anonymized', 'confidential', 'fictional_fixture'] },
    { key: 'customerDisplayName', kind: 'text', required: true },
    { key: 'customerIndustry', kind: 'text', required: true },
    { key: 'marketId', kind: 'reference', required: true, referenceTypes: ['market'] },
    { key: 'productId', kind: 'reference', required: true, referenceTypes: ['product'] },
    { key: 'offerId', kind: 'reference', referenceTypes: ['offer'] },
    { key: 'icpId', kind: 'reference', referenceTypes: ['icp'] },
    { key: 'engagementStartedAt', kind: 'date', required: true },
    { key: 'engagementEndedAt', kind: 'date' },
    { key: 'caseSummary', kind: 'textarea', required: true, span: 'full' },
    { key: 'challenge', kind: 'textarea', required: true, span: 'full' },
    { key: 'approach', kind: 'textarea', required: true, span: 'full' },
    { key: 'outcomes', kind: 'outcomeRows', required: true, span: 'full' },
    { key: 'lessons', kind: 'list', required: true, span: 'full' },
    { key: 'limitations', kind: 'list', required: true, span: 'full' },
    { key: 'approvedUseCases', kind: 'list', required: true, span: 'full' },
    { key: 'authorizationReference', kind: 'text', required: true },
    { key: 'ownerTeam', kind: 'text', required: true },
    { key: 'reviewAt', kind: 'date' },
  ],
}

export interface DecodedStructuredPayload {
  fields: Record<string, string>
  preserved: Record<string, unknown>
}

export function hasStructuredBusinessFields(objectType: BusinessObjectType) {
  return Boolean(structuredBusinessFields[objectType])
}

export function emptyStructuredFieldValues(objectType: BusinessObjectType) {
  return Object.fromEntries((structuredBusinessFields[objectType] ?? []).map((field) => [field.key, '']))
}

export function decodeStructuredPayload(
  objectType: BusinessObjectType,
  payload: Record<string, unknown>,
): DecodedStructuredPayload {
  const definitions = structuredBusinessFields[objectType] ?? []
  const knownKeys = new Set(definitions.map((field) => field.key))
  const fields = Object.fromEntries(definitions.map((field) => [field.key, fieldValue(field, payload[field.key])]))
  const preserved = Object.fromEntries(Object.entries(payload).filter(([key]) => !knownKeys.has(key)))
  return { fields, preserved }
}

export function encodeStructuredPayload(
  objectType: BusinessObjectType,
  fields: Record<string, string>,
  preserved: Record<string, unknown>,
) {
  const payload: Record<string, unknown> = { ...preserved }
  for (const field of structuredBusinessFields[objectType] ?? []) {
    const rawValue = (fields[field.key] ?? '').trim()
    if (!rawValue) {
      delete payload[field.key]
      continue
    }
    if (field.kind === 'list') {
      payload[field.key] = rawValue.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
    } else if (field.kind === 'priceRows') {
      payload[field.key] = parsePriceRows(rawValue)
    } else if (field.kind === 'committeeRows') {
      payload[field.key] = parseCommitteeRows(rawValue)
    } else if (field.kind === 'outcomeRows') {
      payload[field.key] = parseOutcomeRows(rawValue)
    } else {
      payload[field.key] = field.key === 'currency'
        ? normalizedCurrency(rawValue)
        : field.key === 'countryCode'
          ? normalizedCountryCode(rawValue)
          : rawValue
    }
  }
  const validFrom = typeof payload.validFrom === 'string' ? payload.validFrom : null
  const validTo = typeof payload.validTo === 'string' ? payload.validTo : null
  if (validFrom && validTo && validTo < validFrom) throw new BusinessFieldValidationError('dateOrder')
  const engagementStartedAt = typeof payload.engagementStartedAt === 'string' ? payload.engagementStartedAt : null
  const engagementEndedAt = typeof payload.engagementEndedAt === 'string' ? payload.engagementEndedAt : null
  if (engagementStartedAt && engagementEndedAt && engagementEndedAt < engagementStartedAt) {
    throw new BusinessFieldValidationError('engagementDateOrder')
  }
  return payload
}

export function referencedObjects(
  objects: BusinessObject[],
  referenceTypes: BusinessObjectType[] = [],
) {
  const allowed = new Set(referenceTypes)
  return objects.filter((object) => allowed.has(object.objectType) && object.version.status !== 'archived')
}

function normalizedCurrency(value: string) {
  const currency = value.toUpperCase()
  if (!/^[A-Z]{3}$/.test(currency)) throw new BusinessFieldValidationError('currency')
  return currency
}

function normalizedCountryCode(value: string) {
  const countryCode = value.toUpperCase()
  if (!/^[A-Z]{2}$/.test(countryCode)) throw new BusinessFieldValidationError('countryCode')
  return countryCode
}

function parsePriceRows(value: string) {
  return value.split(/\r?\n/).map((row, index) => {
    const [itemReference, rawAmount, unit, ...extra] = row.split('|').map((item) => item.trim())
    if (!itemReference || !rawAmount || !unit || extra.length) {
      throw new BusinessFieldValidationError('priceRow', index + 1)
    }
    const amount = Number(rawAmount)
    if (!Number.isFinite(amount) || amount < 0) throw new BusinessFieldValidationError('priceAmount', index + 1)
    return { itemReference, amount, unit }
  })
}

function parseCommitteeRows(value: string) {
  return value.split(/\r?\n/).map((row, index) => {
    const [role, influence, priorities, ...extra] = row.split('|').map((item) => item.trim())
    if (!role || !influence || !priorities || extra.length) {
      throw new BusinessFieldValidationError('committeeRow', index + 1)
    }
    return { role, influence, priorities }
  })
}

function parseOutcomeRows(value: string) {
  return value.split(/\r?\n/).map((row, index) => {
    const [metric, result, period, evidenceNote, ...extra] = row.split('|').map((item) => item.trim())
    if (!metric || !result || !period || !evidenceNote || extra.length) {
      throw new BusinessFieldValidationError('outcomeRow', index + 1)
    }
    return { metric, result, period, evidenceNote }
  })
}

function fieldValue(field: BusinessFieldDefinition, value: unknown) {
  if (field.kind === 'list') return Array.isArray(value) ? value.map(String).join('\n') : typeof value === 'string' ? value : ''
  if (field.kind === 'priceRows' && Array.isArray(value)) {
    return value.map((entry) => {
      if (!entry || typeof entry !== 'object') return ''
      const row = entry as Record<string, unknown>
      return [row.itemReference, row.amount, row.unit].map((part) => part == null ? '' : String(part)).join(' | ')
    }).filter(Boolean).join('\n')
  }
  if (field.kind === 'committeeRows' && Array.isArray(value)) {
    return value.map((entry) => {
      if (!entry || typeof entry !== 'object') return ''
      const row = entry as Record<string, unknown>
      return [row.role, row.influence, row.priorities].map((part) => part == null ? '' : String(part)).join(' | ')
    }).filter(Boolean).join('\n')
  }
  if (field.kind === 'outcomeRows' && Array.isArray(value)) {
    return value.map((entry) => {
      if (!entry || typeof entry !== 'object') return ''
      const row = entry as Record<string, unknown>
      return [row.metric, row.result, row.period, row.evidenceNote].map((part) => part == null ? '' : String(part)).join(' | ')
    }).filter(Boolean).join('\n')
  }
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}
