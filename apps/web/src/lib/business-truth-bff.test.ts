import { afterEach, describe, expect, it } from 'vitest'
import { DevelopmentIdentityUnavailableError, getBusinessTruthClient } from './business-truth-bff'

const originalSwitch = process.env.GROVELLO_ALLOW_DEVELOPMENT_IDENTITY

afterEach(() => {
  if (originalSwitch === undefined) delete process.env.GROVELLO_ALLOW_DEVELOPMENT_IDENTITY
  else process.env.GROVELLO_ALLOW_DEVELOPMENT_IDENTITY = originalSwitch
})

describe('business truth BFF identity boundary', () => {
  it('rejects development identity unless it is explicitly enabled', () => {
    delete process.env.GROVELLO_ALLOW_DEVELOPMENT_IDENTITY
    expect(() => getBusinessTruthClient()).toThrow(DevelopmentIdentityUnavailableError)
  })

  it('constructs the server-side client only after explicit enablement', () => {
    process.env.GROVELLO_ALLOW_DEVELOPMENT_IDENTITY = 'true'
    expect(() => getBusinessTruthClient()).not.toThrow()
  })
})
