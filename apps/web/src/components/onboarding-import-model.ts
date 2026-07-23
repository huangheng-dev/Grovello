import type {
  BusinessProfile,
  ImportJob,
  ImportMappingFieldInput,
  ImportableBusinessObjectType,
  WorkspaceOnboarding,
} from '@grovello/api-client'

export const defaultRequiredObjectTypes: ImportableBusinessObjectType[] = [
  'brand',
  'product',
  'offer',
  'market',
  'icp',
  'evidence',
]

export const importableObjectTypes: ImportableBusinessObjectType[] = [
  'brand',
  'product',
  'offer',
  'price_book',
  'market',
  'icp',
  'evidence',
  'knowledge_document',
  'case_study',
]

export class OperatorApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message)
  }
}

export async function operatorEnvelope<T>(response: Response) {
  const body = await response.json().catch(() => ({})) as {
    data?: T
    detail?: string
    requestId?: string
    meta?: { source?: 'live' | 'seed'; requestId?: string }
  }
  if (!response.ok || body.data === undefined) {
    throw new OperatorApiError(
      response.status,
      body.detail ?? `HTTP ${response.status}`,
      body.requestId ?? body.meta?.requestId,
    )
  }
  return body as { data: T; meta: { source: 'live' | 'seed'; requestId: string } }
}

export function onboardingCompletedTypes(
  onboarding: WorkspaceOnboarding,
  profile: BusinessProfile,
) {
  const available = new Set(
    profile.objects
      .filter((item) => item.version.status !== 'archived')
      .map((item) => item.objectType),
  )
  return onboarding.requiredObjectTypes.filter((type) => available.has(type))
}

export function onboardingProgress(
  onboarding: WorkspaceOnboarding,
  profile: BusinessProfile,
) {
  if (!onboarding.requiredObjectTypes.length) return 0
  return Math.round(
    onboardingCompletedTypes(onboarding, profile).length
      / onboarding.requiredObjectTypes.length
      * 100,
  )
}

export function isImportPolling(job: ImportJob) {
  return [
    'uploading',
    'uploaded',
    'verifying',
    'scanning',
    'validating',
    'applying',
    'compensating',
  ].includes(job.status)
}

export function canCancelImport(job: ImportJob) {
  return ![
    'completed',
    'partially_completed',
    'failed',
    'cancelled',
    'expired',
    'compensated',
  ].includes(job.status)
}

export function canCompensateImport(job: ImportJob) {
  return ['completed', 'partially_completed'].includes(job.status)
}

export function importProgress(job: ImportJob) {
  return {
    created: 5,
    uploading: 12,
    uploaded: 20,
    verifying: 28,
    scanning: 36,
    ready_for_mapping: 44,
    mapping: 50,
    validating: 60,
    ready_for_review: 72,
    applying: 86,
    completed: 100,
    partially_completed: 100,
    failed: 100,
    cancelled: 100,
    expired: 100,
    compensating: 92,
    compensated: 100,
  }[job.status]
}

export function sourceFieldsFromText(
  text: string,
  format: 'csv' | 'grovello_json',
  delimiter: ',' | ';' | '\t' | '|',
) {
  if (format === 'csv') {
    const firstLine = text.replace(/^\uFEFF/, '').split(/\r?\n/, 1)[0] ?? ''
    const fields = firstLine.split(delimiter).map((item) => item.trim())
    if (!fields.length || fields.some((item) => !item)) {
      throw new Error('invalid_source_fields')
    }
    return fields
  }
  const parsed = JSON.parse(text) as { records?: unknown[] }
  const first = parsed.records?.[0]
  if (!first || typeof first !== 'object' || Array.isArray(first)) {
    throw new Error('invalid_source_fields')
  }
  return [...leafPaths(first as Record<string, unknown>)].sort()
}

export function defaultMappings(fields: string[]): ImportMappingFieldInput[] {
  const canonical = new Set(['canonicalId', 'slug', 'name', 'status', 'locale', 'citations'])
  return fields.map((source) => {
    const candidate = source.trim()
    return {
      source,
      target: canonical.has(candidate) || candidate.startsWith('payload.')
        ? candidate
        : `payload.${candidate.replace(/[^A-Za-z0-9_-]+/g, '_')}`,
      transform: ['slug', 'name', 'status', 'locale'].includes(candidate) ? 'trim' : 'identity',
      hasDefault: false,
      separator: ',',
    }
  })
}

function leafPaths(value: Record<string, unknown>, prefix = ''): Set<string> {
  const paths = new Set<string>()
  Object.entries(value).forEach(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      leafPaths(item as Record<string, unknown>, path).forEach((child) => paths.add(child))
    } else {
      paths.add(path)
    }
  })
  return paths
}
