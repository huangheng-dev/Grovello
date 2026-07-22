import {
  businessTruthErrorResponse,
  getBusinessTruthClient,
} from './business-truth-bff'

export const getAssetClient = getBusinessTruthClient
export const assetErrorResponse = businessTruthErrorResponse
