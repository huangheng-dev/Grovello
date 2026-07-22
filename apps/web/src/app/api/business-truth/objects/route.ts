import { businessTruthErrorResponse, getBusinessTruthClient } from '@/lib/business-truth-bff'
import type { BusinessObjectCreateInput, BusinessTruthMutation } from '@grovello/api-client'
import { NextResponse, type NextRequest } from 'next/server'

export async function POST(request: NextRequest) {
  const idempotencyKey = request.headers.get('Idempotency-Key')
  if (!idempotencyKey) {
    return NextResponse.json({ detail: 'Idempotency-Key is required' }, { status: 400 })
  }
  try {
    const payload = await request.json() as BusinessObjectCreateInput
    const result = await getBusinessTruthClient().post<BusinessTruthMutation>(
      '/business-truth/objects',
      payload,
      idempotencyKey,
    )
    return NextResponse.json(result, { status: 201 })
  } catch (error) {
    return businessTruthErrorResponse(error)
  }
}
