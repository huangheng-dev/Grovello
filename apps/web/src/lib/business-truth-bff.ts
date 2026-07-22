import { GrovelloApiClient, GrovelloApiError } from '@grovello/api-client'
import { randomUUID } from 'node:crypto'
import { NextResponse } from 'next/server'

const northstarWorkspaceId = '00000000-0000-4000-8000-000000000001'

export class DevelopmentIdentityUnavailableError extends Error {}

export function getBusinessTruthClient() {
  if (process.env.GROVELLO_ALLOW_DEVELOPMENT_IDENTITY !== 'true') {
    throw new DevelopmentIdentityUnavailableError(
      'A verified identity provider is not connected and development identity is disabled.',
    )
  }

  const subject = process.env.GROVELLO_DEVELOPMENT_SUBJECT ?? 'northstar-owner'
  const session = process.env.GROVELLO_DEVELOPMENT_SESSION ?? 'local-web-session'
  return new GrovelloApiClient(
    process.env.GROVELLO_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1',
    { workspaceId: process.env.GROVELLO_DEVELOPMENT_WORKSPACE_ID ?? northstarWorkspaceId },
  )
    .withHeaders({
      'X-Grovello-Dev-Subject': subject,
      'X-Grovello-Dev-Session': session,
      'X-Request-ID': randomUUID(),
    })
}

export function businessTruthErrorResponse(error: unknown) {
  if (error instanceof GrovelloApiError) {
    return NextResponse.json(
      { detail: error.detail, requestId: error.requestId },
      { status: error.status },
    )
  }
  if (error instanceof DevelopmentIdentityUnavailableError) {
    return NextResponse.json({ detail: error.message }, { status: 503 })
  }
  return NextResponse.json(
    { detail: 'The Grovello business API is unavailable.' },
    { status: 503 },
  )
}
