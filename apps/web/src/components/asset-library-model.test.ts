import { describe, expect, it } from 'vitest'
import {
  assetNameFromFilename,
  assetSessionProgress,
  assetSlug,
  canCancelAssetSession,
  formatAssetBytes,
  isAssetSessionPolling,
} from './asset-library-model'

describe('asset library model', () => {
  it('creates a stable URL-safe slug from a file name', () => {
    expect(assetSlug(assetNameFromFilename('Servo_Controller Datasheet.pdf')))
      .toBe('servo-controller-datasheet')
  })

  it('keeps durable workflow states explicit', () => {
    expect(isAssetSessionPolling('scanning')).toBe(true)
    expect(isAssetSessionPolling('ready_to_finalize')).toBe(false)
    expect(canCancelAssetSession('verifying')).toBe(true)
    expect(canCancelAssetSession('finalizing')).toBe(false)
    expect(assetSessionProgress('finalized')).toBe(100)
  })

  it('formats bounded file sizes for the operator', () => {
    expect(formatAssetBytes(128)).toBe('128 B')
    expect(formatAssetBytes(2 * 1024 * 1024)).toBe('2.0 MB')
  })
})
