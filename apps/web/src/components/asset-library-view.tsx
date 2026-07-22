'use client'

import type {
  ApiEnvelope,
  AssetCatalog,
  AssetCatalogItem,
  AssetDownload,
  AssetFinalizationInput,
  AssetUploadCreate,
  AssetUploadMutation,
  AssetUploadSession,
} from '@grovello/api-client'
import type { NavigationItem } from '@grovello/product-config'
import { Icon, StatusBadge } from '@grovello/ui'
import { useLocale, useTranslations } from 'next-intl'
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from 'react'
import {
  assetNameFromFilename,
  assetSessionProgress,
  assetSlug,
  canCancelAssetSession,
  defaultAssetMaxBytes,
  formatAssetBytes,
  isAssetSessionPolling,
  sha256File,
  supportedAssetTypes,
} from './asset-library-model'

type LocatedNavigationItem = NavigationItem & { sectionKey: string; sectionSlug: string }

class AssetBrowserError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
  }
}

interface UploadKeys {
  create: string
  complete: string
  cancel: string
  finalize: string
}

interface FinalizeValues {
  name: string
  slug: string
  status: 'draft' | 'active'
  changeSummary: string
}

async function responseEnvelope<T>(response: Response): Promise<ApiEnvelope<T>> {
  const body = await response.json().catch(() => ({})) as ApiEnvelope<T> & { detail?: string }
  if (!response.ok) {
    throw new AssetBrowserError(response.status, body.detail ?? `HTTP ${response.status}`)
  }
  return body
}

function newUploadKeys(): UploadKeys {
  return {
    create: crypto.randomUUID(),
    complete: crypto.randomUUID(),
    cancel: crypto.randomUUID(),
    finalize: crypto.randomUUID(),
  }
}

export function AssetLibraryView({ item }: { item: LocatedNavigationItem }) {
  const t = useTranslations()
  const locale = useLocale() as 'en' | 'zh-CN'
  const [catalog, setCatalog] = useState<AssetCatalog | null>(null)
  const [selected, setSelected] = useState<AssetCatalogItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<AssetBrowserError | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [purpose, setPurpose] = useState('')
  const [targetAssetId, setTargetAssetId] = useState('')
  const [uploadKeys, setUploadKeys] = useState<UploadKeys>(() => newUploadKeys())
  const [session, setSession] = useState<AssetUploadSession | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [finalizeValues, setFinalizeValues] = useState<FinalizeValues>({
    name: '',
    slug: '',
    status: 'draft',
    changeSummary: '',
  })

  const loadCatalog = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/assets', { cache: 'no-store', signal })
      const envelope = await responseEnvelope<AssetCatalog>(response)
      setCatalog(envelope.data)
      setSelected((current) => {
        if (!current) return envelope.data.items[0] ?? null
        return envelope.data.items.find((asset) => asset.id === current.id) ?? envelope.data.items[0] ?? null
      })
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === 'AbortError') return
      setError(loadError instanceof AssetBrowserError
        ? loadError
        : new AssetBrowserError(503, String(loadError)))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const frame = window.requestAnimationFrame(() => void loadCatalog(controller.signal))
    return () => {
      window.cancelAnimationFrame(frame)
      controller.abort()
    }
  }, [loadCatalog])

  const loadDetail = useCallback(async (assetId: string) => {
    setDetailLoading(true)
    try {
      const response = await fetch(`/api/assets/${assetId}`, { cache: 'no-store' })
      const envelope = await responseEnvelope<AssetCatalogItem>(response)
      setSelected(envelope.data)
    } catch (detailError) {
      setNotice(detailError instanceof Error ? detailError.message : t('assets.unknownError'))
    } finally {
      setDetailLoading(false)
    }
  }, [t])

  useEffect(() => {
    if (!session || !isAssetSessionPolling(session.state)) return
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`/api/assets/upload-sessions/${session.id}`, {
          cache: 'no-store',
        })
        const envelope = await responseEnvelope<AssetUploadSession>(response)
        setSession(envelope.data)
        if (envelope.data.state === 'finalized') {
          await loadCatalog()
          if (envelope.data.finalizedAssetId) await loadDetail(envelope.data.finalizedAssetId)
          setNotice(t('assets.finalizedNotice', { name: envelope.data.originalFilename }))
        }
      } catch (pollError) {
        setUploadError(pollError instanceof Error ? pollError.message : t('assets.unknownError'))
      }
    }, 1600)
    return () => window.clearInterval(timer)
  }, [loadCatalog, loadDetail, session, t])

  useEffect(() => {
    if (!uploadOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !uploading) setUploadOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [uploadOpen, uploading])

  const visibleAssets = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return catalog?.items ?? []
    return (catalog?.items ?? []).filter((asset) =>
      `${asset.name} ${asset.slug}`.toLowerCase().includes(normalized),
    )
  }, [catalog?.items, query])

  function openUpload(asset?: AssetCatalogItem) {
    const chosen = asset ?? null
    setFile(null)
    setPurpose('')
    setTargetAssetId(chosen?.id ?? '')
    setUploadKeys(newUploadKeys())
    setSession(null)
    setUploadError(null)
    setFinalizeValues({
      name: chosen?.name ?? '',
      slug: chosen?.slug ?? '',
      status: 'draft',
      changeSummary: '',
    })
    setUploadOpen(true)
  }

  function chooseFile(chosen: File | null) {
    setFile(chosen)
    setUploadError(null)
    if (!chosen) return
    const name = targetAssetId
      ? catalog?.items.find((asset) => asset.id === targetAssetId)?.name ?? ''
      : assetNameFromFilename(chosen.name)
    setFinalizeValues((current) => ({
      ...current,
      name: current.name || name,
      slug: targetAssetId ? current.slug : current.slug || assetSlug(name),
    }))
  }

  async function startUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return
    if (!supportedAssetTypes.has(file.type)) {
      setUploadError(t('assets.unsupportedType'))
      return
    }
    if (file.size > defaultAssetMaxBytes) {
      setUploadError(t('assets.fileTooLarge'))
      return
    }
    setUploading(true)
    setUploadError(null)
    try {
      const checksum = await sha256File(file)
      const createResponse = await fetch('/api/assets/upload-sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': uploadKeys.create },
        body: JSON.stringify({
          originalFilename: file.name,
          contentType: file.type,
          contentLength: file.size,
          checksumSha256: checksum,
          businessPurpose: purpose.trim(),
          targetAssetId: targetAssetId || null,
        }),
      })
      const created = await responseEnvelope<AssetUploadCreate>(createResponse)
      setSession(created.data.session)

      const form = new FormData()
      Object.entries(created.data.upload.fields).forEach(([key, value]) => form.append(key, value))
      form.append('file', file)
      const storageResponse = await fetch(created.data.upload.url, { method: 'POST', body: form })
      if (!storageResponse.ok) {
        throw new AssetBrowserError(storageResponse.status, t('assets.storageUploadFailed'))
      }
      const completeResponse = await fetch(
        `/api/assets/upload-sessions/${created.data.session.id}/complete`,
        { method: 'POST', headers: { 'Idempotency-Key': uploadKeys.complete } },
      )
      const completed = await responseEnvelope<AssetUploadMutation>(completeResponse)
      setSession(completed.data.session)
    } catch (startError) {
      setUploadError(startError instanceof Error ? startError.message : t('assets.unknownError'))
    } finally {
      setUploading(false)
    }
  }

  async function cancelUpload() {
    if (!session) return
    setUploading(true)
    setUploadError(null)
    try {
      const response = await fetch(`/api/assets/upload-sessions/${session.id}/cancel`, {
        method: 'POST',
        headers: { 'Idempotency-Key': uploadKeys.cancel },
      })
      const envelope = await responseEnvelope<AssetUploadMutation>(response)
      setSession(envelope.data.session)
    } catch (cancelError) {
      setUploadError(cancelError instanceof Error ? cancelError.message : t('assets.unknownError'))
    } finally {
      setUploading(false)
    }
  }

  async function finalizeUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!session) return
    setUploading(true)
    setUploadError(null)
    const payload: AssetFinalizationInput = {
      name: finalizeValues.name.trim(),
      slug: targetAssetId ? null : finalizeValues.slug.trim(),
      locale,
      status: finalizeValues.status,
      metadata: {},
      changeSummary: finalizeValues.changeSummary.trim(),
    }
    try {
      const response = await fetch(`/api/assets/upload-sessions/${session.id}/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': uploadKeys.finalize },
        body: JSON.stringify(payload),
      })
      const envelope = await responseEnvelope<AssetUploadMutation>(response)
      setSession(envelope.data.session)
    } catch (finalizeError) {
      setUploadError(finalizeError instanceof Error ? finalizeError.message : t('assets.unknownError'))
    } finally {
      setUploading(false)
    }
  }

  async function downloadVersion(asset: AssetCatalogItem, versionId: string) {
    setNotice(null)
    try {
      const response = await fetch(`/api/assets/${asset.id}/versions/${versionId}/download`, {
        cache: 'no-store',
      })
      const envelope = await responseEnvelope<AssetDownload>(response)
      const link = document.createElement('a')
      link.href = envelope.data.url
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      link.download = envelope.data.filename
      link.click()
      setNotice(t('assets.downloadIssued', { name: envelope.data.filename }))
    } catch (downloadError) {
      setNotice(downloadError instanceof Error ? downloadError.message : t('assets.unknownError'))
    }
  }

  const activeCount = catalog?.items.filter((asset) => asset.status === 'active').length ?? 0
  const versionCount = catalog?.items.reduce((sum, asset) => sum + asset.currentVersion, 0) ?? 0

  return <div className="page-stack asset-library-page">
    <section className="module-hero asset-hero">
      <div>
        <span className="eyebrow">{t(`sections.${item.sectionKey}`)} · {t('assets.governedStorage')}</span>
        <h1>{t('pages.assets.title')}</h1>
        <p>{t('pages.assets.description')}</p>
      </div>
      <button className="button button--primary" onClick={() => openUpload()} disabled={loading || Boolean(error)}>
        <Icon name="upload_file" size={19} />{t('assets.upload')}
      </button>
    </section>

    {notice ? <div className="truth-notice" role="status"><Icon name="info" size={19} /><span>{notice}</span><button className="icon-button" aria-label={t('assets.dismiss')} onClick={() => setNotice(null)}><Icon name="close" size={18} /></button></div> : null}
    {loading ? <AssetState icon="progress_activity" title={t('assets.loading')} body={t('assets.loadingBody')} spinning /> : null}
    {!loading && error ? <AssetState icon={error.status === 401 || error.status === 403 ? 'lock' : 'cloud_off'} title={t(error.status === 401 || error.status === 403 ? 'assets.unauthorizedTitle' : 'assets.unavailableTitle')} body={error.message} action={<button className="button button--secondary" onClick={() => void loadCatalog()}>{t('assets.retry')}</button>} /> : null}
    {!loading && !error && catalog ? <>
      <section className="asset-summary">
        <article><span><Icon name="perm_media" size={21} /></span><div><strong>{catalog.items.length}</strong><small>{t('assets.totalAssets')}</small></div></article>
        <article><span><Icon name="verified" size={21} /></span><div><strong>{activeCount}</strong><small>{t('assets.activeAssets')}</small></div></article>
        <article><span><Icon name="history" size={21} /></span><div><strong>{versionCount}</strong><small>{t('assets.totalVersions')}</small></div></article>
        <article><span><Icon name="shield_lock" size={21} /></span><div><strong>{t('assets.private')}</strong><small>{t('assets.storageBoundary')}</small></div></article>
      </section>

      <section className="asset-toolbar">
        <div><Icon name="search" size={19} /><input type="search" aria-label={t('assets.searchLabel')} placeholder={t('assets.searchPlaceholder')} value={query} onChange={(event) => setQuery(event.target.value)} /></div>
        <span><Icon name="policy" size={17} />{t('assets.approvalBoundary')}</span>
      </section>

      {catalog.items.length ? <div className="asset-layout">
        <section className="panel asset-list-panel">
          <div className="panel-heading"><div><h2>{t('assets.library')}</h2><p>{t('assets.libraryBody')}</p></div><StatusBadge tone="positive">{t('assets.live')}</StatusBadge></div>
          {visibleAssets.length ? <div className="asset-list" aria-label={t('assets.library')}>{visibleAssets.map((asset) => {
            const current = asset.versions[0]
            return <button key={asset.id} type="button" className={`asset-list-item${selected?.id === asset.id ? ' asset-list-item--selected' : ''}`} aria-pressed={selected?.id === asset.id} onClick={() => void loadDetail(asset.id)}>
              <span className="asset-file-icon"><Icon name={current?.originalFile?.contentType.startsWith('image/') ? 'image' : 'description'} size={21} /></span>
              <span><strong>{asset.name}</strong><small>{asset.slug}</small><em>{current?.originalFile ? formatAssetBytes(current.originalFile.byteSize) : t('assets.noFile')} · v{asset.currentVersion}</em></span>
              <StatusBadge tone={asset.status === 'active' ? 'positive' : 'neutral'}>{t(`businessTruth.statuses.${asset.status}`)}</StatusBadge>
            </button>
          })}</div> : <AssetState icon="search_off" title={t('assets.noResults')} body={t('assets.noResultsBody')} compact />}
        </section>

        <section className="panel asset-detail-panel">
          {detailLoading ? <AssetState icon="progress_activity" title={t('assets.loadingVersions')} body={t('assets.loadingVersionsBody')} compact spinning /> : selected ? <>
            <header className="asset-detail-heading"><div><span className="asset-file-icon asset-file-icon--large"><Icon name="folder_open" size={25} /></span><div><small>{t('assets.canonicalAsset')}</small><h2>{selected.name}</h2><p>{selected.slug}</p></div></div><button className="button button--secondary" onClick={() => openUpload(selected)}><Icon name="note_add" size={18} />{t('assets.newVersion')}</button></header>
            <div className="asset-versions"><h3>{t('assets.versionHistory')}</h3>{selected.versions.map((version) => <article key={version.id}>
              <div className="asset-version-main"><span>v{version.version}</span><div><strong>{version.name}</strong><small>{new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(version.createdAt))}</small></div><StatusBadge tone={version.status === 'active' ? 'positive' : 'neutral'}>{t(`businessTruth.statuses.${version.status}`)}</StatusBadge></div>
              {version.originalFile ? <div className="asset-version-file"><span><Icon name="attachment" size={17} />{version.originalFile.filename}</span><span>{formatAssetBytes(version.originalFile.byteSize)}</span><span>{version.originalFile.contentType}</span><span className={version.originalFile.scanStatus === 'clean' ? 'asset-safe' : 'asset-risk'}><Icon name={version.originalFile.scanStatus === 'clean' ? 'verified_user' : 'gpp_bad'} size={16} />{t(`assets.scan.${version.originalFile.scanStatus}`)}</span></div> : <p className="asset-version-missing">{t('assets.noBoundFile')}</p>}
              <footer><p>{version.changeSummary}</p><button className="button button--text" disabled={!version.downloadable} title={!version.downloadable ? t('assets.downloadUnavailable') : undefined} onClick={() => void downloadVersion(selected, version.id)}><Icon name="download" size={17} />{t('assets.download')}</button></footer>
            </article>)}</div>
          </> : <AssetState icon="touch_app" title={t('assets.selectAsset')} body={t('assets.selectAssetBody')} compact />}
        </section>
      </div> : <section className="panel"><AssetState icon="perm_media" title={t('assets.emptyTitle')} body={t('assets.emptyBody')} action={<button className="button button--primary" onClick={() => openUpload()}><Icon name="upload_file" size={18} />{t('assets.uploadFirst')}</button>} /></section>}
    </> : null}

    {uploadOpen ? <div className="modal-backdrop" role="presentation"><div className="modal asset-upload-modal" role="dialog" aria-modal="true" aria-labelledby="asset-upload-title">
      <header><div><span className="eyebrow">{t('assets.governedUpload')}</span><h2 id="asset-upload-title">{targetAssetId ? t('assets.uploadVersionTitle') : t('assets.uploadTitle')}</h2></div><button className="icon-button" type="button" aria-label={t('assets.close')} disabled={uploading} onClick={() => setUploadOpen(false)}><Icon name="close" /></button></header>
      {!session ? <form className="asset-upload-form" onSubmit={startUpload}>
        <label className="asset-dropzone"><input type="file" required accept="image/jpeg,image/png,image/webp,application/pdf" onChange={(event) => chooseFile(event.target.files?.[0] ?? null)} /><span><Icon name="cloud_upload" size={29} /></span><strong>{file?.name ?? t('assets.chooseFile')}</strong><small>{file ? formatAssetBytes(file.size) : t('assets.fileHelp')}</small></label>
        <label className="field-label"><span>{t('assets.targetAsset')}</span><select value={targetAssetId} onChange={(event) => setTargetAssetId(event.target.value)}><option value="">{t('assets.createNewAsset')}</option>{catalog?.items.map((asset) => <option value={asset.id} key={asset.id}>{asset.name}</option>)}</select><small>{t('assets.targetAssetHelp')}</small></label>
        <label className="field-label"><span>{t('assets.businessPurpose')}</span><textarea required minLength={8} maxLength={240} rows={2} value={purpose} onChange={(event) => setPurpose(event.target.value)} /></label>
        {uploadError ? <p className="truth-form-error" role="alert"><Icon name="error" size={18} />{uploadError}</p> : null}
        <footer><button className="button button--secondary" type="button" disabled={uploading} onClick={() => setUploadOpen(false)}>{t('assets.cancel')}</button><button className="button button--primary" type="submit" disabled={!file || uploading}>{uploading ? t('assets.preparing') : t('assets.uploadAndVerify')}</button></footer>
      </form> : <div className="asset-session">
        <div className="asset-session-heading"><span className={`asset-session-icon asset-session-icon--${session.state}`}><Icon name={session.state === 'finalized' ? 'task_alt' : session.state === 'failed' || session.state === 'quarantined' ? 'error' : 'progress_activity'} size={25} /></span><div><small>{t('assets.durableWorkflow')}</small><h3>{t(`assets.states.${session.state}`)}</h3><p>{session.originalFilename}</p></div></div>
        <div className="asset-progress" aria-label={t('assets.progressLabel')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={assetSessionProgress(session.state)} role="progressbar"><span style={{ width: `${assetSessionProgress(session.state)}%` }} /></div>
        <ol className="asset-steps"><li className="is-complete">{t('assets.stepUploaded')}</li><li className={['scanning', 'ready_to_finalize', 'finalizing', 'finalized'].includes(session.state) ? 'is-complete' : ''}>{t('assets.stepVerified')}</li><li className={['ready_to_finalize', 'finalizing', 'finalized'].includes(session.state) ? 'is-complete' : ''}>{t('assets.stepScanned')}</li><li className={session.state === 'finalized' ? 'is-complete' : ''}>{t('assets.stepFinalized')}</li></ol>
        {session.state === 'ready_to_finalize' ? <form className="asset-finalize-form" onSubmit={finalizeUpload}>
          <div className="truth-editor__grid"><label className="field-label"><span>{t('assets.assetName')}</span><input required maxLength={200} value={finalizeValues.name} onChange={(event) => setFinalizeValues({ ...finalizeValues, name: event.target.value })} /></label><label className="field-label"><span>{t('assets.assetStatus')}</span><select value={finalizeValues.status} onChange={(event) => setFinalizeValues({ ...finalizeValues, status: event.target.value as 'draft' | 'active' })}><option value="draft">{t('businessTruth.statuses.draft')}</option><option value="active">{t('businessTruth.statuses.active')}</option></select></label>{!targetAssetId ? <label className="field-label"><span>{t('assets.assetSlug')}</span><input required minLength={2} maxLength={120} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={finalizeValues.slug} onChange={(event) => setFinalizeValues({ ...finalizeValues, slug: event.target.value })} /></label> : null}</div>
          <label className="field-label"><span>{t('assets.changeSummary')}</span><textarea required minLength={8} maxLength={500} rows={2} value={finalizeValues.changeSummary} onChange={(event) => setFinalizeValues({ ...finalizeValues, changeSummary: event.target.value })} /></label>
          <p className="asset-approval-note"><Icon name="policy" size={18} />{t(finalizeValues.status === 'active' ? 'assets.activeApprovalNote' : 'assets.draftApprovalNote')}</p>
          <button className="button button--primary" type="submit" disabled={uploading}>{uploading ? t('assets.finalizing') : t('assets.finalize')}</button>
        </form> : null}
        {['quarantined', 'failed', 'expired', 'cancelled'].includes(session.state) ? <p className="truth-form-error" role="alert"><Icon name="gpp_bad" size={18} />{session.failureDetail ?? t(`assets.terminal.${session.state}`)}</p> : null}
        {uploadError ? <p className="truth-form-error" role="alert"><Icon name="error" size={18} />{uploadError}</p> : null}
        <footer><button className="button button--secondary" type="button" onClick={() => setUploadOpen(false)}>{session.state === 'finalized' ? t('assets.done') : t('assets.close')}</button>{canCancelAssetSession(session.state) ? <button className="button button--text asset-cancel" type="button" disabled={uploading} onClick={() => void cancelUpload()}>{t('assets.cancelWorkflow')}</button> : null}</footer>
      </div>}
    </div></div> : null}
  </div>
}

function AssetState({ icon, title, body, action, compact = false, spinning = false }: { icon: string; title: string; body: string; action?: React.ReactNode; compact?: boolean; spinning?: boolean }) {
  return <div className={`truth-state asset-state${compact ? ' asset-state--compact' : ''}`}><span className={spinning ? 'asset-state-spinner' : ''}><Icon name={icon} size={28} /></span><h2>{title}</h2><p>{body}</p>{action}</div>
}
