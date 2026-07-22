import { assetErrorResponse, getAssetClient } from '@/lib/asset-bff'
import type { AssetFinalizationInput, AssetUploadMutation } from '@grovello/api-client'
import { NextResponse, type NextRequest } from 'next/server'

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ uploadSessionId: string }> },
) {
  const idempotencyKey = request.headers.get('Idempotency-Key')
  if (!idempotencyKey) {
    return NextResponse.json({ detail: 'Idempotency-Key is required' }, { status: 400 })
  }
  const { uploadSessionId } = await params
  try {
    const payload = await request.json() as AssetFinalizationInput
    const result = await getAssetClient().post<AssetUploadMutation>(
      `/assets/upload-sessions/${uploadSessionId}/finalize`,
      payload,
      idempotencyKey,
    )
    return NextResponse.json(result, { status: 202 })
  } catch (error) {
    return assetErrorResponse(error)
  }
}
