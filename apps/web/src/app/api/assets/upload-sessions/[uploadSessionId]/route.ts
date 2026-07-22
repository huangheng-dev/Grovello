import { assetErrorResponse, getAssetClient } from '@/lib/asset-bff'
import type { AssetUploadSession } from '@grovello/api-client'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ uploadSessionId: string }> },
) {
  const { uploadSessionId } = await params
  try {
    const result = await getAssetClient().get<AssetUploadSession>(
      `/assets/upload-sessions/${uploadSessionId}`,
      { cache: 'no-store' },
    )
    return NextResponse.json(result)
  } catch (error) {
    return assetErrorResponse(error)
  }
}
