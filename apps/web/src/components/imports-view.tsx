'use client'

import type {
  ImportChangeSet,
  ImportChangeSetMutation,
  ImportJob,
  ImportJobCreate,
  ImportJobMutation,
  ImportMappingFieldInput,
  ImportMappingMutation,
  ImportValidationReport,
  ImportWorkflowMutation,
  ImportableBusinessObjectType,
} from '@grovello/api-client'
import type { NavigationItem } from '@grovello/product-config'
import { Icon, StatusBadge } from '@grovello/ui'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import { sha256File } from './asset-library-model'
import {
  canCancelImport,
  canCompensateImport,
  defaultMappings,
  importableObjectTypes,
  importProgress,
  isImportPolling,
  OperatorApiError,
  operatorEnvelope,
  sourceFieldsFromText,
} from './onboarding-import-model'

type LocatedNavigationItem = NavigationItem & { sectionKey: string; sectionSlug: string }
type SourceFormat = 'csv' | 'grovello_json'
type Delimiter = ',' | ';' | '\t' | '|'

const maxImportBytes = 25 * 1024 * 1024

export function ImportsView({ item }: { item: LocatedNavigationItem }) {
  const t = useTranslations()
  const locale = useLocale() as 'en' | 'zh-CN'
  const [jobs, setJobs] = useState<ImportJob[]>([])
  const [selected, setSelected] = useState<ImportJob | null>(null)
  const [report, setReport] = useState<ImportValidationReport | null>(null)
  const [changeSet, setChangeSet] = useState<ImportChangeSet | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<OperatorApiError | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [objectType, setObjectType] = useState<ImportableBusinessObjectType>('product')
  const [purpose, setPurpose] = useState('')
  const [delimiter, setDelimiter] = useState<Delimiter>(',')
  const [sourceFields, setSourceFields] = useState<string[]>([])
  const [sourceFieldsText, setSourceFieldsText] = useState('')
  const [mappings, setMappings] = useState<ImportMappingFieldInput[]>([])
  const [policyVersion, setPolicyVersion] = useState('1')
  const [approvalReason, setApprovalReason] = useState('')
  const [compensationPurpose, setCompensationPurpose] = useState('')

  const loadJobs = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/imports', { cache: 'no-store', signal })
      const envelope = await operatorEnvelope<ImportJob[]>(response)
      setJobs(envelope.data)
      setSelected((current) => {
        if (current) return envelope.data.find((job) => job.id === current.id) ?? envelope.data[0] ?? null
        return envelope.data[0] ?? null
      })
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === 'AbortError') return
      setError(asOperatorError(loadError))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (jobId: string, quiet = false) => {
    if (!quiet) setDetailLoading(true)
    setActionError(null)
    try {
      const response = await fetch(`/api/imports/${jobId}`, { cache: 'no-store' })
      const envelope = await operatorEnvelope<ImportJob>(response)
      const job = envelope.data
      setSelected(job)
      setJobs((current) => current.map((item) => item.id === job.id ? job : item))

      if (['ready_for_review', 'applying', 'completed', 'partially_completed', 'compensating', 'compensated'].includes(job.status)) {
        const validationResponse = await fetch(`/api/imports/${job.id}/validation`, { cache: 'no-store' })
        if (validationResponse.ok) {
          setReport((await operatorEnvelope<ImportValidationReport>(validationResponse)).data)
        } else {
          setReport(null)
        }
        if (job.selectedChangeSetId) {
          const changeSetResponse = await fetch(`/api/imports/${job.id}/change-set`, { cache: 'no-store' })
          if (changeSetResponse.ok) {
            setChangeSet((await operatorEnvelope<ImportChangeSet>(changeSetResponse)).data)
          } else {
            setChangeSet(null)
          }
        } else {
          setChangeSet(null)
        }
      } else {
        setReport(null)
        setChangeSet(null)
      }
    } catch (detailError) {
      setActionError(operatorMessage(t, detailError))
    } finally {
      if (!quiet) setDetailLoading(false)
    }
  }, [t])

  useEffect(() => {
    const controller = new AbortController()
    const frame = requestAnimationFrame(() => void loadJobs(controller.signal))
    return () => {
      cancelAnimationFrame(frame)
      controller.abort()
    }
  }, [loadJobs])

  useEffect(() => {
    if (!selected) return
    const frame = requestAnimationFrame(() => void loadDetail(selected.id))
    return () => cancelAnimationFrame(frame)
    // The selected identity intentionally drives detail loading, not status refreshes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id])

  useEffect(() => {
    if (!selected || !isImportPolling(selected)) return
    const timer = window.setInterval(() => void loadDetail(selected.id, true), 1600)
    return () => window.clearInterval(timer)
  }, [loadDetail, selected])

  const statusCounts = useMemo(() => ({
    total: jobs.length,
    active: jobs.filter((job) => isImportPolling(job) || ['ready_for_mapping', 'ready_for_review'].includes(job.status)).length,
    failed: jobs.filter((job) => ['failed', 'partially_completed'].includes(job.status)).length,
    completed: jobs.filter((job) => ['completed', 'compensated'].includes(job.status)).length,
  }), [jobs])

  function resetCreate() {
    setFile(null)
    setObjectType('product')
    setPurpose('')
    setDelimiter(',')
    setSourceFields([])
    setSourceFieldsText('')
    setMappings([])
    setActionError(null)
  }

  async function chooseFile(chosen: File | null) {
    setActionError(null)
    if (!chosen) {
      setFile(null)
      return
    }
    try {
      if (chosen.size > maxImportBytes) throw new Error(t('imports.fileTooLarge'))
      const format = sourceFormat(chosen)
      const text = await chosen.text()
      setFile(chosen)
      const fields = sourceFieldsFromText(text, format, delimiter)
      setSourceFields(fields)
      setSourceFieldsText(fields.join(', '))
      setMappings(defaultMappings(fields))
    } catch (fileError) {
      setFile(null)
      setSourceFields([])
      setSourceFieldsText('')
      setMappings([])
      setActionError(fileError instanceof Error ? localSourceMessage(t, fileError.message) : t('imports.unknownError'))
    }
  }

  async function createImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return
    setBusy(true)
    setActionError(null)
    try {
      const format = sourceFormat(file)
      const checksum = await sha256File(file)
      const createResponse = await fetch('/api/imports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({
          objectType,
          sourceFormat: format,
          schemaVersion: 1,
          locale,
          originalFilename: file.name,
          contentType: format === 'csv' ? 'text/csv' : 'application/json',
          contentLength: file.size,
          checksumSha256: checksum,
          businessPurpose: purpose.trim(),
          inputVersions: { operatorExperience: 'p2-d4-v1' },
        }),
      })
      const created = await operatorEnvelope<ImportJobCreate>(createResponse)
      const form = new FormData()
      Object.entries(created.data.upload.fields).forEach(([key, value]) => form.append(key, value))
      form.append('file', file)
      const storageResponse = await fetch(created.data.upload.url, { method: 'POST', body: form })
      if (!storageResponse.ok) throw new OperatorApiError(storageResponse.status, t('imports.storageUploadFailed'))
      const completeResponse = await postImportAction<ImportJobMutation>(
        created.data.job.id,
        'complete',
        {},
      )
      setJobs((current) => [completeResponse.data.job, ...current.filter((job) => job.id !== completeResponse.data.job.id)])
      setSelected(completeResponse.data.job)
      setCreateOpen(false)
      setNotice(t('imports.uploadStartedNotice', { name: file.name }))
    } catch (createError) {
      setActionError(operatorMessage(t, createError))
    } finally {
      setBusy(false)
    }
  }

  function syncMappingsFromText() {
    const fields = sourceFieldsText.split(',').map((field) => field.trim()).filter(Boolean)
    setSourceFields(fields)
    setMappings((current) => fields.map((field) =>
      current.find((mapping) => mapping.source === field) ?? defaultMappings([field])[0]!,
    ))
  }

  function updateMapping(index: number, patch: Partial<ImportMappingFieldInput>) {
    setMappings((current) => current.map((mapping, mappingIndex) =>
      mappingIndex === index ? { ...mapping, ...patch } : mapping,
    ))
  }

  async function saveMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected) return
    await runAction(async () => {
      const envelope = await postImportAction<ImportMappingMutation>(selected.id, 'mapping', {
        sourceFields,
        delimiter: selected.sourceFormat === 'csv' ? delimiter : null,
        fields: mappings,
        businessPurpose: purpose.trim() || selected.businessPurpose,
      })
      setNotice(t('imports.mappingSavedNotice', { version: envelope.data.mapping.version }))
      await loadDetail(selected.id, true)
    })
  }

  async function startValidation() {
    if (!selected) return
    await runAction(async () => {
      const envelope = await postImportAction<ImportJobMutation>(selected.id, 'validation', {
        businessPurpose: purpose.trim() || selected.businessPurpose,
      })
      setSelected(envelope.data.job)
      setNotice(t('imports.validationStartedNotice'))
    })
  }

  async function createChangeSet() {
    if (!selected) return
    await runAction(async () => {
      const envelope = await postImportAction<ImportChangeSetMutation>(selected.id, 'change-set', {
        businessPurpose: purpose.trim() || selected.businessPurpose,
        policyVersion: policyVersion ? Number(policyVersion) : null,
      })
      setChangeSet(envelope.data.changeSet)
      setNotice(t('imports.changeSetCreatedNotice', { version: envelope.data.changeSet.version }))
    })
  }

  async function decide(decision: 'approved' | 'rejected') {
    if (!selected) return
    await runAction(async () => {
      const envelope = await postImportAction<ImportChangeSetMutation>(selected.id, 'approval', {
        decision,
        reason: approvalReason.trim(),
        policyVersion: Number(policyVersion),
      })
      setChangeSet(envelope.data.changeSet)
      setNotice(t(decision === 'approved' ? 'imports.approvedNotice' : 'imports.rejectedNotice'))
    })
  }

  async function applyChangeSet() {
    if (!selected) return
    await runAction(async () => {
      const envelope = await postImportAction<ImportWorkflowMutation>(selected.id, 'apply', {})
      setChangeSet(envelope.data.changeSet)
      setNotice(t('imports.applyStartedNotice'))
      await loadDetail(selected.id, true)
    })
  }

  async function cancelJob() {
    if (!selected) return
    await runAction(async () => {
      const envelope = await postImportAction<ImportJobMutation>(selected.id, 'cancel', {})
      setSelected(envelope.data.job)
      setNotice(t('imports.cancelledNotice'))
    })
  }

  async function compensate() {
    if (!selected) return
    await runAction(async () => {
      await postImportAction<ImportWorkflowMutation>(selected.id, 'compensate', {
        businessPurpose: compensationPurpose.trim(),
        policyVersion: Number(policyVersion),
      })
      setNotice(t('imports.compensationStartedNotice'))
      await loadDetail(selected.id, true)
    })
  }

  async function runAction(action: () => Promise<void>) {
    setBusy(true)
    setActionError(null)
    try {
      await action()
    } catch (actionFailure) {
      setActionError(operatorMessage(t, actionFailure))
    } finally {
      setBusy(false)
    }
  }

  return <div className="page-stack imports-page">
    <section className="module-hero imports-hero">
      <div><span className="eyebrow">{t(`sections.${item.sectionKey}`)} · {t('imports.foundationLabel')}</span><h1>{t(`pages.${item.key}.title`)}</h1><p>{t(`pages.${item.key}.description`)}</p></div>
      <div className="imports-hero__actions">
        <Link className="button button--secondary" href={`/${locale}/brand/business-setup`}><Icon name="checklist" size={18} />{t('imports.openSetup')}</Link>
        <button className="button button--primary" onClick={() => { resetCreate(); setCreateOpen(true) }}><Icon name="upload_file" size={19} />{t('imports.newImport')}</button>
      </div>
    </section>

    {notice ? <div className="truth-notice" role="status"><Icon name="check_circle" size={19} /><span>{notice}</span><button className="icon-button" aria-label={t('imports.dismiss')} onClick={() => setNotice(null)}><Icon name="close" size={18} /></button></div> : null}
    {loading ? <ImportState icon="progress_activity" title={t('imports.loading')} body={t('imports.loadingBody')} spinning /> : null}
    {!loading && error ? <ImportState icon={error.status === 401 || error.status === 403 ? 'lock' : 'cloud_off'} title={t(error.status === 401 || error.status === 403 ? 'imports.unauthorizedTitle' : 'imports.unavailableTitle')} body={operatorMessage(t, error)} action={<button className="button button--secondary" onClick={() => void loadJobs()}><Icon name="refresh" size={18} />{t('imports.retry')}</button>} /> : null}

    {!loading && !error ? <>
      <section className="setup-summary imports-summary">
        <Summary icon="folder_open" value={statusCounts.total} label={t('imports.totalJobs')} />
        <Summary icon="pending_actions" value={statusCounts.active} label={t('imports.activeJobs')} />
        <Summary icon="error" value={statusCounts.failed} label={t('imports.attentionJobs')} />
        <Summary icon="task_alt" value={statusCounts.completed} label={t('imports.completedJobs')} />
      </section>

      <div className="imports-layout">
        <section className="panel imports-list-panel">
          <div className="panel-heading"><div><h2>{t('imports.jobsTitle')}</h2><p>{t('imports.jobsBody')}</p></div></div>
          {jobs.length ? <div className="imports-list">{jobs.map((job) => <button key={job.id} className={`imports-list-item ${selected?.id === job.id ? 'is-selected' : ''}`} onClick={() => setSelected(job)}>
            <span><Icon name={jobStatusIcon(job)} size={20} /></span>
            <div><strong>{job.source.originalFilename}</strong><small>{t(`businessTruth.objectTypes.${job.objectType}`)} · {t(`imports.statuses.${job.status}`)}</small><em>{formatDate(locale, job.createdAt)}</em></div>
            <StatusBadge tone={jobStatusTone(job)}>{t(`imports.statuses.${job.status}`)}</StatusBadge>
          </button>)}</div> : <div className="truth-empty truth-empty--compact"><span><Icon name="upload_file" size={27} /></span><h3>{t('imports.emptyTitle')}</h3><p>{t('imports.emptyBody')}</p><button className="button button--secondary" onClick={() => setCreateOpen(true)}>{t('imports.newImport')}</button></div>}
        </section>

        <section className="panel imports-detail-panel">
          {detailLoading ? <ImportState icon="progress_activity" title={t('imports.detailLoading')} body={t('imports.detailLoadingBody')} spinning /> : selected ? <ImportDetail
            job={selected}
            report={report}
            changeSet={changeSet}
            busy={busy}
            actionError={actionError}
            locale={locale}
            delimiter={delimiter}
            sourceFieldsText={sourceFieldsText}
            mappings={mappings}
            policyVersion={policyVersion}
            approvalReason={approvalReason}
            compensationPurpose={compensationPurpose}
            setDelimiter={setDelimiter}
            setSourceFieldsText={setSourceFieldsText}
            syncMappingsFromText={syncMappingsFromText}
            updateMapping={updateMapping}
            setPolicyVersion={setPolicyVersion}
            setApprovalReason={setApprovalReason}
            setCompensationPurpose={setCompensationPurpose}
            saveMapping={saveMapping}
            startValidation={startValidation}
            createChangeSet={createChangeSet}
            decide={decide}
            applyChangeSet={applyChangeSet}
            cancelJob={cancelJob}
            compensate={compensate}
          /> : <ImportState icon="touch_app" title={t('imports.selectTitle')} body={t('imports.selectBody')} />}
        </section>
      </div>
    </> : null}

    {createOpen ? <div className="modal-backdrop" role="presentation" onMouseDown={() => !busy && setCreateOpen(false)}><form className="modal import-create-modal" role="dialog" aria-modal="true" aria-labelledby="import-create-title" onSubmit={createImport} onMouseDown={(event) => event.stopPropagation()}>
      <header><div><span className="eyebrow">{t('imports.secureIntake')}</span><h2 id="import-create-title">{t('imports.createTitle')}</h2></div><button type="button" className="icon-button" aria-label={t('imports.close')} disabled={busy} onClick={() => setCreateOpen(false)}><Icon name="close" /></button></header>
      <label className="asset-dropzone"><input required type="file" accept=".csv,.json,text/csv,application/json" onChange={(event) => void chooseFile(event.target.files?.[0] ?? null)} /><span><Icon name="upload_file" size={28} /></span><strong>{file?.name ?? t('imports.chooseFile')}</strong><small>{t('imports.fileHelp')}</small></label>
      <div className="truth-editor__grid">
        <label className="field-label"><span>{t('imports.objectType')}</span><select value={objectType} onChange={(event) => setObjectType(event.target.value as ImportableBusinessObjectType)}>{importableObjectTypes.map((type) => <option value={type} key={type}>{t(`businessTruth.objectTypes.${type}`)}</option>)}</select></label>
        <label className="field-label"><span>{t('imports.csvDelimiter')}</span><select value={delimiter} disabled={Boolean(file && sourceFormat(file) !== 'csv')} onChange={(event) => setDelimiter(event.target.value as Delimiter)}><option value=",">{t('imports.delimiters.comma')}</option><option value=";">{t('imports.delimiters.semicolon')}</option><option value="|">{t('imports.delimiters.pipe')}</option><option value={'\t'}>{t('imports.delimiters.tab')}</option></select></label>
      </div>
      <label className="field-label"><span>{t('imports.businessPurpose')}</span><textarea required minLength={8} maxLength={240} rows={2} value={purpose} onChange={(event) => setPurpose(event.target.value)} /></label>
      {sourceFields.length ? <p className="asset-approval-note"><Icon name="schema" size={17} />{t('imports.detectedFields', { count: sourceFields.length, fields: sourceFields.join(', ') })}</p> : null}
      {actionError ? <p className="truth-form-error" role="alert"><Icon name="error" size={18} />{actionError}</p> : null}
      <footer><button type="button" className="button button--secondary" disabled={busy} onClick={() => setCreateOpen(false)}>{t('imports.cancel')}</button><button className="button button--primary" disabled={busy || !file || !sourceFields.length}>{busy ? t('imports.uploading') : t('imports.uploadAndVerify')}</button></footer>
    </form></div> : null}
  </div>
}

function ImportDetail(props: {
  job: ImportJob
  report: ImportValidationReport | null
  changeSet: ImportChangeSet | null
  busy: boolean
  actionError: string | null
  locale: string
  delimiter: Delimiter
  sourceFieldsText: string
  mappings: ImportMappingFieldInput[]
  policyVersion: string
  approvalReason: string
  compensationPurpose: string
  setDelimiter: (value: Delimiter) => void
  setSourceFieldsText: (value: string) => void
  syncMappingsFromText: () => void
  updateMapping: (index: number, patch: Partial<ImportMappingFieldInput>) => void
  setPolicyVersion: (value: string) => void
  setApprovalReason: (value: string) => void
  setCompensationPurpose: (value: string) => void
  saveMapping: (event: FormEvent<HTMLFormElement>) => void
  startValidation: () => void
  createChangeSet: () => void
  decide: (decision: 'approved' | 'rejected') => void
  applyChangeSet: () => void
  cancelJob: () => void
  compensate: () => void
}) {
  const t = useTranslations()
  const { job, report, changeSet } = props
  return <div className="import-detail">
    <header className="import-detail__heading">
      <div><span className={`import-job-icon import-job-icon--${job.status}`}><Icon name={jobStatusIcon(job)} size={23} /></span><div><small>{t(`businessTruth.objectTypes.${job.objectType}`)}</small><h2>{job.source.originalFilename}</h2><p>{job.businessPurpose}</p></div></div>
      <StatusBadge tone={jobStatusTone(job)}>{t(`imports.statuses.${job.status}`)}</StatusBadge>
    </header>
    <div className="asset-progress" role="progressbar" aria-label={t('imports.progress')} aria-valuenow={importProgress(job)} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${importProgress(job)}%` }} /></div>
    <dl className="import-meta">
      <div><dt>{t('imports.sourceFormat')}</dt><dd>{job.sourceFormat === 'csv' ? 'CSV' : 'Grovello JSON'}</dd></div>
      <div><dt>{t('imports.scanStatus')}</dt><dd>{t(`imports.scanStatuses.${job.source.scanStatus}`)}</dd></div>
      <div><dt>{t('imports.rows')}</dt><dd>{job.validRows}/{job.totalRows}</dd></div>
      <div><dt>{t('imports.retention')}</dt><dd>{formatDate(props.locale, job.retentionDeadline)}</dd></div>
    </dl>

    {job.failureCode ? <div className="import-alert import-alert--critical" role="alert"><Icon name="error" size={20} /><div><strong>{job.failureCode}</strong><p>{job.failureDetail ?? t('imports.failureFallback')}</p></div></div> : null}
    {props.actionError ? <p className="truth-form-error" role="alert"><Icon name="error" size={18} />{props.actionError}</p> : null}

    {job.status === 'ready_for_mapping' && !job.selectedMappingVersionId ? <form className="import-stage" onSubmit={props.saveMapping}>
      <div><span className="import-stage__number">1</span><div><h3>{t('imports.mappingTitle')}</h3><p>{t('imports.mappingBody')}</p></div></div>
      <label className="field-label"><span>{t('imports.sourceFields')}</span><textarea required rows={2} value={props.sourceFieldsText} onBlur={props.syncMappingsFromText} onChange={(event) => props.setSourceFieldsText(event.target.value)} /><small>{t('imports.sourceFieldsHelp')}</small></label>
      {job.sourceFormat === 'csv' ? <label className="field-label"><span>{t('imports.csvDelimiter')}</span><select value={props.delimiter} onChange={(event) => props.setDelimiter(event.target.value as Delimiter)}><option value=",">{t('imports.delimiters.comma')}</option><option value=";">{t('imports.delimiters.semicolon')}</option><option value="|">{t('imports.delimiters.pipe')}</option><option value={'\t'}>{t('imports.delimiters.tab')}</option></select></label> : null}
      <div className="import-mappings">
        {props.mappings.map((mapping, index) => <div key={`${mapping.source}-${index}`}>
          <span>{mapping.source}</span><Icon name="arrow_forward" size={17} />
          <input aria-label={t('imports.targetFor', { source: mapping.source ?? '' })} required value={mapping.target} onChange={(event) => props.updateMapping(index, { target: event.target.value })} />
          <select aria-label={t('imports.transformFor', { source: mapping.source ?? '' })} value={mapping.transform} onChange={(event) => props.updateMapping(index, { transform: event.target.value as ImportMappingFieldInput['transform'] })}>{['identity', 'trim', 'lowercase', 'uppercase', 'integer', 'decimal', 'boolean', 'json', 'split'].map((transform) => <option value={transform} key={transform}>{t(`imports.transforms.${transform}`)}</option>)}</select>
        </div>)}
      </div>
      <button className="button button--primary" disabled={props.busy || !props.mappings.length}><Icon name="save" size={18} />{t('imports.saveMapping')}</button>
    </form> : null}

    {(job.status === 'mapping' || (job.status === 'ready_for_mapping' && job.selectedMappingVersionId)) ? <section className="import-stage"><div><span className="import-stage__number">2</span><div><h3>{t('imports.validationTitle')}</h3><p>{t('imports.validationReadyBody')}</p></div></div><button className="button button--primary" disabled={props.busy} onClick={props.startValidation}><Icon name="rule" size={18} />{t('imports.startValidation')}</button></section> : null}

    {['verifying', 'scanning', 'validating', 'applying', 'compensating'].includes(job.status) ? <div className="import-alert"><span className="truth-spinner" /><div><strong>{t(`imports.statuses.${job.status}`)}</strong><p>{t(`imports.processing.${job.status}`)}</p></div></div> : null}

    {report ? <section className="import-stage">
      <div><span className="import-stage__number">3</span><div><h3>{t('imports.reviewTitle')}</h3><p>{t('imports.reviewBody', { valid: report.job.validRows, invalid: report.job.invalidRows })}</p></div></div>
      {report.issues.length ? <div className="import-issues">{report.issues.slice(0, 8).map((issue, index) => <article key={`${issue.code}-${issue.sourceRowNumber}-${index}`}><Icon name={issue.severity === 'warning' ? 'warning' : 'error'} size={18} /><div><strong>{issue.code}</strong><p>{issue.message}</p><small>{issue.sourceRowNumber ? t('imports.rowNumber', { number: issue.sourceRowNumber }) : t('imports.fileLevel')}</small></div></article>)}</div> : <div className="setup-ready"><Icon name="verified" size={22} /><div><strong>{t('imports.validationClean')}</strong><p>{t('imports.validationCleanBody')}</p></div></div>}
      <div className="import-preview" tabIndex={0} aria-label={t('imports.previewTitle')}>
        <table><thead><tr><th>{t('imports.row')}</th><th>{t('imports.state')}</th><th>{t('imports.normalizedData')}</th></tr></thead><tbody>{report.preview.slice(0, 12).map((row) => <tr key={row.sourceRowNumber}><td>{row.sourceRowNumber}</td><td><StatusBadge tone={row.status === 'valid' ? 'positive' : row.status === 'duplicate' ? 'neutral' : 'warning'}>{row.status}</StatusBadge></td><td><code>{JSON.stringify(row.normalizedData)}</code></td></tr>)}</tbody></table>
      </div>
      {!changeSet && job.status === 'ready_for_review' ? <div className="import-policy-row"><label className="field-label"><span>{t('imports.policyVersionOptional')}</span><input min={1} type="number" value={props.policyVersion} onChange={(event) => props.setPolicyVersion(event.target.value)} /></label><button className="button button--primary" disabled={props.busy} onClick={props.createChangeSet}><Icon name="difference" size={18} />{t('imports.createChangeSet')}</button></div> : null}
    </section> : null}

    {changeSet ? <section className="import-stage">
      <div><span className="import-stage__number">4</span><div><h3>{t('imports.changeSetTitle', { version: changeSet.version })}</h3><p>{t('imports.changeSetBody', { hash: changeSet.planHash.slice(0, 12) })}</p></div></div>
      <div className="import-change-summary">{Object.entries(changeSet.summary).map(([key, value]) => <article key={key}><strong>{value}</strong><small>{t(`imports.operations.${key}`)}</small></article>)}</div>
      {changeSet.approvalState === 'pending' ? <div className="import-approval">
        <label className="field-label"><span>{t('imports.policyVersion')}</span><input required min={1} type="number" value={props.policyVersion} onChange={(event) => props.setPolicyVersion(event.target.value)} /></label>
        <label className="field-label"><span>{t('imports.approvalReason')}</span><textarea required minLength={8} rows={2} value={props.approvalReason} onChange={(event) => props.setApprovalReason(event.target.value)} /></label>
        <div><button className="button button--secondary" disabled={props.busy || props.approvalReason.trim().length < 8} onClick={() => props.decide('rejected')}>{t('imports.reject')}</button><button className="button button--primary" disabled={props.busy || props.approvalReason.trim().length < 8} onClick={() => props.decide('approved')}><Icon name="approval" size={18} />{t('imports.approve')}</button></div>
      </div> : null}
      {['not_required', 'approved'].includes(changeSet.approvalState) && job.status === 'ready_for_review' ? <button className="button button--primary" disabled={props.busy} onClick={props.applyChangeSet}><Icon name="play_circle" size={18} />{t('imports.applyChangeSet')}</button> : null}
    </section> : null}

    {canCompensateImport(job) ? <section className="import-stage import-stage--risk"><div><span className="import-stage__number"><Icon name="history" size={18} /></span><div><h3>{t('imports.compensationTitle')}</h3><p>{t('imports.compensationBody')}</p></div></div><label className="field-label"><span>{t('imports.compensationPurpose')}</span><textarea required minLength={8} rows={2} value={props.compensationPurpose} onChange={(event) => props.setCompensationPurpose(event.target.value)} /></label><div className="import-policy-row"><label className="field-label"><span>{t('imports.policyVersion')}</span><input required min={1} type="number" value={props.policyVersion} onChange={(event) => props.setPolicyVersion(event.target.value)} /></label><button className="button button--secondary import-risk-action" disabled={props.busy || props.compensationPurpose.trim().length < 8} onClick={props.compensate}><Icon name="undo" size={18} />{t('imports.startCompensation')}</button></div></section> : null}

    <footer className="import-detail__footer">
      <span>{t('imports.updatedAt', { date: formatDate(props.locale, job.updatedAt) })}</span>
      {canCancelImport(job) ? <button className="button button--text import-risk-action" disabled={props.busy} onClick={props.cancelJob}><Icon name="cancel" size={17} />{t('imports.cancelJob')}</button> : null}
    </footer>
  </div>
}

function Summary({ icon, value, label }: { icon: string; value: number; label: string }) {
  return <article><span><Icon name={icon} size={20} /></span><div><strong>{value}</strong><small>{label}</small></div></article>
}

function ImportState({ icon, title, body, action, spinning = false }: { icon: string; title: string; body: string; action?: ReactNode; spinning?: boolean }) {
  return <div className="truth-state import-state" aria-live="polite"><span className={spinning ? 'truth-spinner' : undefined}>{spinning ? null : <Icon name={icon} size={28} />}</span><h2>{title}</h2><p>{body}</p>{action}</div>
}

async function postImportAction<T>(jobId: string, action: string, body: unknown) {
  const response = await fetch(`/api/imports/${jobId}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
    body: JSON.stringify(body),
  })
  return operatorEnvelope<T>(response)
}

function sourceFormat(file: File): SourceFormat {
  if (file.type === 'text/csv' || file.name.toLowerCase().endsWith('.csv')) return 'csv'
  if (file.type === 'application/json' || file.name.toLowerCase().endsWith('.json')) return 'grovello_json'
  throw new Error('unsupported_source')
}

function localSourceMessage(t: ReturnType<typeof useTranslations>, code: string) {
  if (code === 'invalid_source_fields') return t('imports.invalidSourceFields')
  if (code === 'unsupported_source') return t('imports.unsupportedSource')
  return code
}

function asOperatorError(error: unknown) {
  return error instanceof OperatorApiError ? error : new OperatorApiError(503, String(error))
}

function operatorMessage(t: ReturnType<typeof useTranslations>, error: unknown) {
  if (error instanceof OperatorApiError) {
    if (error.status === 401 || error.status === 403) return t('imports.unauthorizedBody')
    if (error.status === 409) return t('imports.conflictBody')
    if (error.status === 422) return t('imports.validationErrorBody', { detail: error.message })
    if (error.status === 503) return t('imports.unavailableBody')
    return t('imports.requestFailed', { status: error.status })
  }
  return error instanceof Error ? localSourceMessage(t, error.message) : t('imports.unknownError')
}

function jobStatusTone(job: ImportJob): 'positive' | 'warning' | 'neutral' {
  if (['completed', 'compensated'].includes(job.status)) return 'positive'
  if (['failed', 'partially_completed', 'cancelled'].includes(job.status)) return 'warning'
  return 'neutral'
}

function jobStatusIcon(job: ImportJob) {
  if (['completed', 'compensated'].includes(job.status)) return 'task_alt'
  if (['failed', 'partially_completed'].includes(job.status)) return 'error'
  if (job.status === 'cancelled') return 'cancel'
  if (isImportPolling(job)) return 'progress_activity'
  return 'description'
}

function formatDate(locale: string, value: string) {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
