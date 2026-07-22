import { businessTruthErrorResponse, getBusinessTruthClient } from '@/lib/business-truth-bff'
import type { BusinessProfile } from '@grovello/api-client'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const profile = await getBusinessTruthClient().get<BusinessProfile>('/business-truth/profile', {
      cache: 'no-store',
    })
    return NextResponse.json(profile)
  } catch (error) {
    return businessTruthErrorResponse(error)
  }
}
