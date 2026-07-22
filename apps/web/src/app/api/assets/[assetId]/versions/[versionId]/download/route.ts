import { assetErrorResponse, getAssetClient } from '@/lib/asset-bff'
import type { AssetDownload } from '@grovello/api-client'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ assetId: string; versionId: string }> },
) {
  const { assetId, versionId } = await params
  try {
    const result = await getAssetClient().get<AssetDownload>(
      `/assets/${assetId}/versions/${versionId}/download`,
      { cache: 'no-store' },
    )
    return NextResponse.json(result)
  } catch (error) {
    return assetErrorResponse(error)
  }
}
