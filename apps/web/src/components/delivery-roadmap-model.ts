export type DeliveryStageStatus = 'verified' | 'inProgress' | 'current' | 'planned'

export interface DeliveryStage {
  phase: number
  icon: string
  status: DeliveryStageStatus
}

export const deliveryStages: DeliveryStage[] = [
  { phase: 0, icon: 'foundation', status: 'verified' },
  { phase: 1, icon: 'shield_person', status: 'inProgress' },
  { phase: 2, icon: 'database', status: 'current' },
  { phase: 3, icon: 'flag', status: 'planned' },
  { phase: 4, icon: 'extension', status: 'planned' },
  { phase: 5, icon: 'rocket_launch', status: 'planned' },
  { phase: 6, icon: 'person_search', status: 'planned' },
  { phase: 7, icon: 'forum', status: 'planned' },
  { phase: 8, icon: 'handshake', status: 'planned' },
  { phase: 9, icon: 'payments', status: 'planned' },
  { phase: 10, icon: 'loyalty', status: 'planned' },
  { phase: 11, icon: 'monitoring', status: 'planned' },
  { phase: 12, icon: 'psychology', status: 'planned' },
  { phase: 13, icon: 'deployed_code', status: 'planned' },
]

export function deliveryStageCounts(stages = deliveryStages) {
  return stages.reduce((counts, stage) => ({
    ...counts,
    [stage.status]: counts[stage.status] + 1,
  }), { verified: 0, inProgress: 0, current: 0, planned: 0 })
}

export function isSequentialDeliveryRoadmap(stages = deliveryStages) {
  return stages.every((stage, index) => stage.phase === index)
}
