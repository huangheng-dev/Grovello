import {
  getOnboardingImportClient,
  onboardingImportErrorResponse,
  optionalJson,
  requestIdempotencyKey,
} from '@/lib/onboarding-import-bff'
import type {
  WorkspaceOnboarding,
  WorkspaceOnboardingCreateInput,
  WorkspaceOnboardingMutation,
} from '@grovello/api-client'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const response = await getOnboardingImportClient().get<WorkspaceOnboarding>(
      '/workspace-onboarding',
      { cache: 'no-store' },
    )
    return NextResponse.json(response)
  } catch (error) {
    return onboardingImportErrorResponse(error)
  }
}

export async function POST(request: Request) {
  try {
    const response = await getOnboardingImportClient().post<WorkspaceOnboardingMutation>(
      '/workspace-onboarding',
      await optionalJson(request) as WorkspaceOnboardingCreateInput,
      requestIdempotencyKey(request),
    )
    return NextResponse.json(response, { status: 201 })
  } catch (error) {
    return onboardingImportErrorResponse(error)
  }
}
