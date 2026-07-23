import {
  getOnboardingImportClient,
  onboardingImportErrorResponse,
  optionalJson,
  requestIdempotencyKey,
} from '@/lib/onboarding-import-bff'
import type {
  WorkspaceOnboardingActivationInput,
  WorkspaceOnboardingMutation,
} from '@grovello/api-client'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const response = await getOnboardingImportClient().post<WorkspaceOnboardingMutation>(
      '/workspace-onboarding/activate',
      await optionalJson(request) as WorkspaceOnboardingActivationInput,
      requestIdempotencyKey(request),
    )
    return NextResponse.json(response)
  } catch (error) {
    return onboardingImportErrorResponse(error)
  }
}
