import {
  getOnboardingImportClient,
  onboardingImportErrorResponse,
  optionalJson,
  requestIdempotencyKey,
} from '@/lib/onboarding-import-bff'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const actionPaths = {
  complete: 'complete',
  mapping: 'mapping',
  validation: 'validation',
  'change-set': 'change-set',
  approval: 'change-set/approval',
  apply: 'apply',
  cancel: 'cancel',
  compensate: 'compensate',
} as const

type Action = keyof typeof actionPaths

function resolveAction(value: string): Action | null {
  return value in actionPaths ? value as Action : null
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ jobId: string; action: string }> },
) {
  const { jobId, action: rawAction } = await params
  const action = resolveAction(rawAction)
  if (!action || !['validation', 'change-set'].includes(action)) {
    return NextResponse.json({ detail: 'Unsupported import query.' }, { status: 404 })
  }
  try {
    const response = await getOnboardingImportClient().get(
      `/import-jobs/${jobId}/${actionPaths[action]}`,
      { cache: 'no-store' },
    )
    return NextResponse.json(response)
  } catch (error) {
    return onboardingImportErrorResponse(error)
  }
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ jobId: string; action: string }> },
) {
  const { jobId, action: rawAction } = await params
  const action = resolveAction(rawAction)
  if (!action) {
    return NextResponse.json({ detail: 'Unsupported import action.' }, { status: 404 })
  }
  try {
    const response = await getOnboardingImportClient().post(
      `/import-jobs/${jobId}/${actionPaths[action]}`,
      await optionalJson(request),
      requestIdempotencyKey(request),
    )
    return NextResponse.json(response, {
      status: ['complete', 'validation', 'apply', 'compensate'].includes(action) ? 202 : undefined,
    })
  } catch (error) {
    return onboardingImportErrorResponse(error)
  }
}
