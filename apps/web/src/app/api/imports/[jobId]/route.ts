import {
  getOnboardingImportClient,
  onboardingImportErrorResponse,
} from '@/lib/onboarding-import-bff'
import type { ImportJob } from '@grovello/api-client'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  try {
    const { jobId } = await params
    const response = await getOnboardingImportClient().get<ImportJob>(
      `/import-jobs/${jobId}`,
      { cache: 'no-store' },
    )
    return NextResponse.json(response)
  } catch (error) {
    return onboardingImportErrorResponse(error)
  }
}
