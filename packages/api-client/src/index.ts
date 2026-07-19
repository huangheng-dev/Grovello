export interface ApiMeta {
  source: 'live' | 'seed'
  generatedAt: string
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
}

export class GrovelloApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly context: ApiRequestContext = {},
  ) {}

  async get<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: init?.credentials ?? 'include',
      headers: {
        Accept: 'application/json',
        ...(this.context.workspaceId ? { 'X-Workspace-ID': this.context.workspaceId } : {}),
        ...init?.headers,
      },
    })
    if (!response.ok) throw new Error(`Grovello API request failed: ${response.status}`)
    return response.json() as Promise<ApiEnvelope<T>>
  }
}
