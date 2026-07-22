import type { AssetUploadState } from '@grovello/api-client'

export const supportedAssetTypes = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'application/pdf',
])

export const defaultAssetMaxBytes = 100 * 1024 * 1024

export function assetSlug(value: string) {
  return value
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 120)
}

export function assetNameFromFilename(filename: string) {
  const withoutExtension = filename.replace(/\.[^.]+$/, '')
  return withoutExtension.replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim()
}

export function formatAssetBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export function isAssetSessionPolling(state: AssetUploadState) {
  return ['uploaded', 'verifying', 'scanning', 'finalizing'].includes(state)
}

export function canCancelAssetSession(state: AssetUploadState) {
  return ['initiated', 'uploaded', 'verifying', 'scanning'].includes(state)
}

export function assetSessionProgress(state: AssetUploadState) {
  return {
    initiated: 15,
    uploaded: 35,
    verifying: 45,
    scanning: 65,
    ready_to_finalize: 78,
    finalizing: 90,
    finalized: 100,
    quarantined: 100,
    failed: 100,
    expired: 100,
    cancelled: 100,
  }[state]
}

export async function sha256File(file: File) {
  const bytes = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}
