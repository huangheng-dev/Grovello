import {
  businessTruthErrorResponse,
  getBusinessTruthClient,
} from './business-truth-bff'

export const getOnboardingImportClient = getBusinessTruthClient
export const onboardingImportErrorResponse = businessTruthErrorResponse

export function requestIdempotencyKey(request: Request) {
  return request.headers.get('Idempotency-Key') ?? crypto.randomUUID()
}

export async function optionalJson(request: Request) {
  return request.json().catch(() => ({}))
}
