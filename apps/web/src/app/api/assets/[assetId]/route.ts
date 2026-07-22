import { assetErrorResponse, getAssetClient } from '@/lib/asset-bff'
import type { AssetCatalogItem } from '@grovello/api-client'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ assetId: string }> },
) {
  const { assetId } = await params
  try {
    const result = await getAssetClient().get<AssetCatalogItem>(`/assets/${assetId}`, {
      cache: 'no-store',
    })
    return NextResponse.json(result)
  } catch (error) {
    return assetErrorResponse(error)
  }
}
