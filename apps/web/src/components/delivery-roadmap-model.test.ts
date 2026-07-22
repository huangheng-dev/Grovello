import { describe, expect, it } from 'vitest'
import { deliveryStageCounts, deliveryStages, isSequentialDeliveryRoadmap } from './delivery-roadmap-model'

describe('delivery roadmap', () => {
  it('retains all fourteen sequential delivery gates', () => {
    expect(deliveryStages).toHaveLength(14)
    expect(isSequentialDeliveryRoadmap()).toBe(true)
  })

  it('marks only verified gates as complete', () => {
    expect(deliveryStageCounts()).toEqual({ verified: 1, inProgress: 1, current: 1, planned: 11 })
  })

  it('keeps shared business truth as the current delivery focus', () => {
    expect(deliveryStages.find((stage) => stage.status === 'current')?.phase).toBe(2)
  })
})
