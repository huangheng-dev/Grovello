import { assetErrorResponse, getAssetClient } from '@/lib/asset-bff'
import type { AssetUploadCreate, AssetUploadCreateInput } from '@grovello/api-client'
import { NextResponse, type NextRequest } from 'next/server'

export async function POST(request: NextRequest) {
  const idempotencyKey = request.headers.get('Idempotency-Key')
  if (!idempotencyKey) {
    return NextResponse.json({ detail: 'Idempotency-Key is required' }, { status: 400 })
  }
  try {
    const payload = await request.json() as AssetUploadCreateInput
    const result = await getAssetClient().post<AssetUploadCreate>(
      '/assets/upload-sessions',
      payload,
      idempotencyKey,
    )
    return NextResponse.json(result, { status: 201 })
  } catch (error) {
    return assetErrorResponse(error)
  }
}
