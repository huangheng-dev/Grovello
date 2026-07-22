import type { BusinessObject, BusinessObjectType, BusinessProfile } from '@grovello/api-client'

const requiredProfileObjectTypes: BusinessObjectType[] = [
  'brand',
  'product',
  'offer',
  'price_book',
  'market',
  'icp',
  'evidence',
  'knowledge_document',
  'asset',
  'case_study',
]

export const businessTruthTypesByPage: Record<string, BusinessObjectType[]> = {
  brandRules: ['brand'],
  products: ['product', 'offer', 'price_book'],
  markets: ['market'],
  icp: ['icp'],
  knowledge: ['evidence', 'knowledge_document', 'knowledge_chunk', 'case_study'],
  assets: ['asset'],
}

export const businessTruthCreateTypesByPage: Record<string, BusinessObjectType[]> = {
  ...businessTruthTypesByPage,
  knowledge: ['evidence', 'knowledge_document', 'case_study'],
}

export function slugifyBusinessObjectName(value: string) {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 120)
}

export function objectsForCapability(
  objects: BusinessObject[],
  itemKey: string,
) {
  const allowed = new Set(businessTruthTypesByPage[itemKey] ?? [])
  return objects.filter((object) => allowed.has(object.objectType))
}

export function filterBusinessTruthObjects(
  objects: BusinessObject[],
  query: string,
  objectType: BusinessObjectType | 'all',
) {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  return objects.filter((object) => {
    if (objectType !== 'all' && object.objectType !== objectType) return false
    if (!normalizedQuery) return true
    const searchable = [
      object.version.name,
      object.slug,
      object.version.businessPurpose,
      JSON.stringify(object.version.payload),
      ...object.version.citations.flatMap((citation) => [citation.evidenceName, citation.claimText]),
    ].join(' ').toLocaleLowerCase()
    return searchable.includes(normalizedQuery)
  })
}

export function profileAfterMutation(profile: BusinessProfile, nextObject: BusinessObject): BusinessProfile {
  const previousIndex = profile.objects.findIndex((object) => object.id === nextObject.id)
  const objects = previousIndex === -1
    ? [...profile.objects, nextObject]
    : profile.objects.map((object) => object.id === nextObject.id ? nextObject : object)
  const activeTypes = new Set(
    objects.filter((object) => object.version.status === 'active').map((object) => object.objectType),
  )
  const missingObjectTypes = requiredProfileObjectTypes.filter((type) => !activeTypes.has(type))
  const citationCount = objects.reduce((count, object) => count + object.version.citations.length, 0)
  return {
    ...profile,
    objects,
    objectCount: objects.length,
    citationCount,
    missingObjectTypes,
    validationState: missingObjectTypes.length === 0 && citationCount > 0 ? 'complete' : 'incomplete',
  }
}
