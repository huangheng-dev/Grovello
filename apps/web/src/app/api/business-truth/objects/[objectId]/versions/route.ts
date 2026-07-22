import { businessTruthErrorResponse, getBusinessTruthClient } from '@/lib/business-truth-bff'
import type { BusinessObjectVersionCreateInput, BusinessTruthMutation } from '@grovello/api-client'
import { NextResponse, type NextRequest } from 'next/server'

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ objectId: string }> },
) {
  const idempotencyKey = request.headers.get('Idempotency-Key')
  if (!idempotencyKey) {
    return NextResponse.json({ detail: 'Idempotency-Key is required' }, { status: 400 })
  }
  try {
    const { objectId } = await params
    const payload = await request.json() as BusinessObjectVersionCreateInput
    const result = await getBusinessTruthClient().post<BusinessTruthMutation>(
      `/business-truth/objects/${encodeURIComponent(objectId)}/versions`,
      payload,
      idempotencyKey,
    )
    return NextResponse.json(result, { status: 201 })
  } catch (error) {
    return businessTruthErrorResponse(error)
  }
}
