export interface ApiMeta {
  source: 'live' | 'seed'
  generatedAt: string
  requestId: string
}

export interface ApiEnvelope<T> {
  data: T
  meta: ApiMeta
}

export interface HealthStatus {
  status: 'ok' | 'degraded'
  service: string
  version: string
  environment: string
  checkedAt: string
}

export interface ApiRequestContext {
  workspaceId?: string
  headers?: Record<string, string>
}

export type BusinessObjectType =
  | 'brand'
  | 'product'
  | 'offer'
  | 'price_book'
  | 'market'
  | 'icp'
  | 'evidence'
  | 'knowledge_document'
  | 'knowledge_chunk'
  | 'asset'
  | 'case_study'

export type BusinessObjectStatus = 'draft' | 'active' | 'archived'
export type BusinessTruthSource = 'owner_edit' | 'import' | 'seed'

export interface BusinessTruthCitation {
  id: string
  evidenceObjectId: string
  evidenceVersionId: string
  evidenceVersion: number
  evidenceName: string
  claimText: string
  locator: Record<string, unknown>
}

export interface BusinessObjectVersion {
  id: string
  version: number
  schemaVersion: number
  name: string
  status: BusinessObjectStatus
  locale: string
  payload: Record<string, unknown>
  businessPurpose: string
  actorId: string
  sourceType: BusinessTruthSource
  sourceRef: string | null
  changeSummary: string
  inputVersions: Record<string, unknown>
  createdAt: string
  citations: BusinessTruthCitation[]
}

export interface BusinessObject {
  id: string
  workspaceId: string
  objectType: BusinessObjectType
  slug: string
  currentVersion: number
  version: BusinessObjectVersion
}

export interface BusinessProfile {
  workspaceId: string
  validationState: 'complete' | 'incomplete'
  objectCount: number
  citationCount: number
  missingObjectTypes: BusinessObjectType[]
  objects: BusinessObject[]
}

export interface BusinessTruthMutation {
  object: BusinessObject
  idempotentReplay: boolean
}

export type ImportableBusinessObjectType = Exclude<
  BusinessObjectType,
  'knowledge_chunk' | 'asset'
>

export interface WorkspaceOnboarding {
  id: string
  workspaceId: string
  status: 'draft' | 'in_progress' | 'ready_for_review' | 'active' | 'blocked'
  businessPurpose: string
  requiredObjectTypes: ImportableBusinessObjectType[]
  validationGaps: Record<string, unknown>[]
  inputVersions: Record<string, unknown>
  lastCompletedStep: string | null
  policyVersion: number | null
  activationVersion: number
  activatedBy: string | null
  activatedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface WorkspaceOnboardingCreateInput {
  businessPurpose: string
  requiredObjectTypes: ImportableBusinessObjectType[]
  inputVersions: Record<string, unknown>
}

export interface WorkspaceOnboardingMutation {
  onboarding: WorkspaceOnboarding
  idempotentReplay: boolean
}

export type ImportJobStatus =
  | 'created'
  | 'uploading'
  | 'uploaded'
  | 'verifying'
  | 'scanning'
  | 'ready_for_mapping'
  | 'mapping'
  | 'validating'
  | 'ready_for_review'
  | 'applying'
  | 'completed'
  | 'partially_completed'
  | 'failed'
  | 'cancelled'
  | 'expired'
  | 'compensating'
  | 'compensated'

export interface ImportSource {
  id: string
  state: 'uploading' | 'uploaded' | 'verifying' | 'scanning' | 'clean' | 'quarantined' | 'failed' | 'cancelled' | 'expired' | 'deleted'
  originalFilename: string
  declaredMimeType: string
  declaredSize: number
  declaredSha256: string
  verifiedSize: number | null
  verifiedMimeType: string | null
  verifiedSha256: string | null
  verifiedAt: string | null
  scanStatus: 'not_started' | 'pending' | 'clean' | 'infected' | 'failed'
  scanProvider: string | null
  scanReference: string | null
  scanAttempts: number
  scannedAt: string | null
  quarantinedAt: string | null
  expiresAt: string
  deletionDeadline: string
  deletedAt: string | null
}

export interface ImportJob {
  id: string
  workspaceId: string
  actorId: string
  businessPurpose: string
  objectType: ImportableBusinessObjectType
  sourceFormat: 'csv' | 'grovello_json'
  schemaVersion: number
  locale: string
  status: ImportJobStatus
  totalRows: number
  validRows: number
  invalidRows: number
  appliedRows: number
  workflowId: string | null
  inputVersions: Record<string, unknown>
  resultSummary: Record<string, unknown>
  failureCode: string | null
  failureDetail: string | null
  retentionDeadline: string
  cancelledAt: string | null
  completedAt: string | null
  createdAt: string
  updatedAt: string
  source: ImportSource
}

export interface ImportJobCreateInput {
  objectType: ImportableBusinessObjectType
  sourceFormat: 'csv' | 'grovello_json'
  schemaVersion: number
  locale: 'en' | 'zh-CN'
  originalFilename: string
  contentType: 'text/csv' | 'application/json'
  contentLength: number
  checksumSha256: string
  businessPurpose: string
  inputVersions: Record<string, unknown>
}

export interface ImportJobCreate {
  job: ImportJob
  upload: AssetUploadGrant
  idempotentReplay: boolean
}

export interface ImportJobMutation {
  job: ImportJob
  idempotentReplay: boolean
}

export interface BusinessTruthCitationInput {
  evidenceVersionId: string
  claimText: string
  locator: Record<string, unknown>
}

export interface BusinessObjectCreateInput {
  objectType: BusinessObjectType
  slug: string
  name: string
  status: BusinessObjectStatus
  locale: string
  payload: Record<string, unknown>
  businessPurpose: string
  changeSummary: string
  sourceType: BusinessTruthSource
  sourceRef?: string | null
  inputVersions: Record<string, unknown>
  citations: BusinessTruthCitationInput[]
}

export type BusinessObjectVersionCreateInput = Omit<BusinessObjectCreateInput, 'objectType' | 'slug'>

export type AssetUploadState =
  | 'initiated'
  | 'uploaded'
  | 'verifying'
  | 'scanning'
  | 'ready_to_finalize'
  | 'finalizing'
  | 'finalized'
  | 'quarantined'
  | 'failed'
  | 'expired'
  | 'cancelled'

export interface AssetUploadSession {
  id: string
  workspaceId: string
  targetAssetId: string | null
  actorId: string
  businessPurpose: string
  state: AssetUploadState
  scanStatus: 'not_started' | 'pending' | 'clean' | 'infected' | 'failed'
  scanProvider: string | null
  scanReference: string | null
  scanAttempts: number
  scannedAt: string | null
  finalizationWorkflowId: string | null
  finalizedBlobId: string | null
  finalizedAssetId: string | null
  finalizedAssetVersionId: string | null
  finalizedAt: string | null
  stagingCleanupStatus: 'not_started' | 'pending' | 'complete' | 'failed'
  stagingCleanupAt: string | null
  originalFilename: string
  declaredMimeType: string
  declaredSize: number
  declaredSha256: string
  expiresAt: string
  completedAt: string | null
  cancelledAt: string | null
  workflowId: string | null
  failureCode: string | null
  failureDetail: string | null
  verifiedSize: number | null
  verifiedSha256: string | null
  verifiedMimeType: string | null
  verifiedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface AssetUploadGrant {
  method: 'POST'
  url: string
  fields: Record<string, string>
  expiresAt: string
}

export interface AssetUploadCreate {
  session: AssetUploadSession
  upload: AssetUploadGrant
  idempotentReplay: boolean
}

export interface AssetUploadMutation {
  session: AssetUploadSession
  idempotentReplay: boolean
}

export interface AssetUploadCreateInput {
  originalFilename: string
  contentType: string
  contentLength: number
  checksumSha256: string
  businessPurpose: string
  targetAssetId?: string | null
}

export interface AssetFinalizationInput {
  name: string
  slug?: string | null
  locale: 'en' | 'zh-CN'
  status: 'draft' | 'active'
  metadata: Record<string, unknown>
  changeSummary: string
}

export interface AssetFile {
  blobId: string
  filename: string
  contentType: string
  byteSize: number
  sha256: string
  scanStatus: 'pending' | 'clean' | 'infected' | 'failed'
  storageStatus: 'available' | 'quarantined' | 'purge_pending' | 'purged'
}

export interface AssetCatalogVersion {
  id: string
  version: number
  name: string
  status: BusinessObjectStatus
  locale: string
  payload: Record<string, unknown>
  changeSummary: string
  createdAt: string
  originalFile: AssetFile | null
  downloadable: boolean
}

export interface AssetCatalogItem {
  id: string
  slug: string
  name: string
  status: BusinessObjectStatus
  currentVersion: number
  updatedAt: string
  versions: AssetCatalogVersion[]
}

export interface AssetCatalog {
  items: AssetCatalogItem[]
}

export interface AssetDownload {
  assetId: string
  assetVersionId: string
  blobId: string
  filename: string
  contentType: string
  byteSize: number
  sha256: string
  url: string
  expiresAt: string
  headers: Record<string, string>
}

export class GrovelloApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly requestId?: string,
  ) {
    super(detail)
    this.name = 'GrovelloApiError'
  }
}

async function apiResponse<T>(response: Response): Promise<ApiEnvelope<T>> {
  const body = await response.json().catch(() => undefined) as
    | ApiEnvelope<T>
    | { detail?: unknown; requestId?: string }
    | undefined
  if (!response.ok) {
    const error = body as { detail?: unknown; requestId?: string } | undefined
    const detail = typeof error?.detail === 'string'
      ? error.detail
      : error?.detail
        ? JSON.stringify(error.detail)
        : `Grovello API request failed: ${response.status}`
    throw new GrovelloApiError(
      response.status,
      detail,
      error?.requestId ?? response.headers.get('X-Request-ID') ?? undefined,
    )
  }
  return body as ApiEnvelope<T>
}

export class GrovelloApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly context: ApiRequestContext = {},
  ) {}

  withHeaders(headers: Record<string, string>) {
    return new GrovelloApiClient(this.baseUrl, {
      ...this.context,
      headers: { ...this.context.headers, ...headers },
    })
  }

  async get<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: init?.credentials ?? 'include',
      headers: {
        Accept: 'application/json',
        ...(this.context.workspaceId ? { 'X-Workspace-ID': this.context.workspaceId } : {}),
        ...this.context.headers,
        ...init?.headers,
      },
    })
    return apiResponse<T>(response)
  }

  async post<T>(
    path: string,
    body: unknown,
    idempotencyKey: string,
    init?: RequestInit,
  ): Promise<ApiEnvelope<T>> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      method: 'POST',
      credentials: init?.credentials ?? 'include',
      body: JSON.stringify(body),
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
        ...(this.context.workspaceId ? { 'X-Workspace-ID': this.context.workspaceId } : {}),
        ...this.context.headers,
        ...init?.headers,
      },
    })
    return apiResponse<T>(response)
  }
}
