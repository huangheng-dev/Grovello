import { assetErrorResponse, getAssetClient } from '@/lib/asset-bff'
import type { AssetCatalog } from '@grovello/api-client'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const result = await getAssetClient().get<AssetCatalog>('/assets', { cache: 'no-store' })
    return NextResponse.json(result)
  } catch (error) {
    return assetErrorResponse(error)
  }
}
