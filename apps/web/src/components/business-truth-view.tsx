'use client'

import type {
  ApiEnvelope,
  BusinessObject,
  BusinessObjectCreateInput,
  BusinessObjectStatus,
  BusinessObjectType,
  BusinessObjectVersionCreateInput,
  BusinessProfile,
  BusinessTruthMutation,
} from '@grovello/api-client'
import type { NavigationItem } from '@grovello/product-config'
import { Icon, StatusBadge } from '@grovello/ui'
import { useLocale, useTranslations } from 'next-intl'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  BusinessCitationValidationError,
  citationLocatorParts,
  decodeBusinessCitations,
  emptyBusinessCitation,
  encodeBusinessCitations,
  evidenceVersionOptions,
  type CitationLocatorKind,
  type EditableBusinessCitation,
} from './business-truth-citations'
import {
  BusinessFieldValidationError,
  decodeStructuredPayload,
  emptyStructuredFieldValues,
  encodeStructuredPayload,
  hasStructuredBusinessFields,
  referencedObjects,
  structuredBusinessFields,
  type BusinessFieldDefinition,
} from './business-truth-fields'
import {
  businessTruthCreateTypesByPage,
  businessTruthTypesByPage,
  filterBusinessTruthObjects,
  objectsForCapability,
  profileAfterMutation,
  slugifyBusinessObjectName,
} from './business-truth-model'

type LocatedNavigationItem = NavigationItem & { sectionKey: string; sectionSlug: string }

interface EditorState {
  mode: 'create' | 'version'
  idempotencyKey: string
  object?: BusinessObject
}

interface EditorValues {
  objectType: BusinessObjectType
  name: string
  slug: string
  status: BusinessObjectStatus
  locale: string
  businessPurpose: string
  changeSummary: string
  payloadJson: string
  fieldValues: Record<string, string>
  preservedPayload: Record<string, unknown>
  citations: EditableBusinessCitation[]
}

class BrowserApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
  }
}

async function responseEnvelope<T>(response: Response): Promise<ApiEnvelope<T>> {
  const body = await response.json().catch(() => ({})) as ApiEnvelope<T> & { detail?: string }
  if (!response.ok) throw new BrowserApiError(response.status, body.detail ?? `HTTP ${response.status}`)
  return body
}

function initialValues(itemKey: string, locale: string, object?: BusinessObject): EditorValues {
  const objectType = object?.objectType ?? businessTruthCreateTypesByPage[itemKey]?.[0] ?? 'brand'
  const payload = object?.version.payload ?? {}
  const structured = decodeStructuredPayload(objectType, payload)
  if (object) {
    return {
      objectType,
      name: object.version.name,
      slug: object.slug,
      status: object.version.status,
      locale: object.version.locale,
      businessPurpose: object.version.businessPurpose,
      changeSummary: '',
      payloadJson: JSON.stringify(payload, null, 2),
      fieldValues: structured.fields,
      preservedPayload: structured.preserved,
      citations: decodeBusinessCitations(object.version.citations, () => crypto.randomUUID()),
    }
  }
  return {
    objectType,
    name: '',
    slug: '',
    status: 'draft',
    locale,
    businessPurpose: '',
    changeSummary: '',
    payloadJson: '{\n  \n}',
    fieldValues: emptyStructuredFieldValues(objectType),
    preservedPayload: {},
    citations: [],
  }
}

export function BusinessTruthView({ item }: { item: LocatedNavigationItem }) {
  const t = useTranslations()
  const locale = useLocale()
  const [profile, setProfile] = useState<BusinessProfile | null>(null)
  const [source, setSource] = useState<'live' | 'seed' | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<BrowserApiError | null>(null)
  const [editor, setEditor] = useState<EditorState | null>(null)
  const [values, setValues] = useState<EditorValues>(() => initialValues(item.key, locale))
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [retrievalQuery, setRetrievalQuery] = useState('')
  const [retrievalType, setRetrievalType] = useState<BusinessObjectType | 'all'>('all')

  const loadProfile = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/business-truth/profile', { cache: 'no-store', signal })
      const envelope = await responseEnvelope<BusinessProfile>(response)
      setProfile(envelope.data)
      setSource(envelope.meta.source)
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === 'AbortError') return
      setError(loadError instanceof BrowserApiError ? loadError : new BrowserApiError(503, String(loadError)))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const frame = window.requestAnimationFrame(() => void loadProfile(controller.signal))
    return () => {
      window.cancelAnimationFrame(frame)
      controller.abort()
    }
  }, [loadProfile])

  const objects = useMemo(
    () => objectsForCapability(profile?.objects ?? [], item.key),
    [item.key, profile?.objects],
  )
  const objectTypes = businessTruthCreateTypesByPage[item.key] ?? []
  const visibleObjects = useMemo(
    () => filterBusinessTruthObjects(objects, retrievalQuery, retrievalType),
    [objects, retrievalQuery, retrievalType],
  )
  const retrievalTypes = businessTruthTypesByPage[item.key] ?? []
  const showRetrieval = item.key === 'knowledge'

  function openCreate() {
    setValues(initialValues(item.key, locale))
    setFormError(null)
    setEditor({ mode: 'create', idempotencyKey: crypto.randomUUID() })
  }

  function openVersion(object: BusinessObject) {
    setValues(initialValues(item.key, locale, object))
    setFormError(null)
    setEditor({ mode: 'version', object, idempotencyKey: crypto.randomUUID() })
  }

  function updateName(name: string) {
    setValues((current) => ({
      ...current,
      name,
      slug: editor?.mode === 'create' && (!current.slug || current.slug === slugifyBusinessObjectName(current.name))
        ? slugifyBusinessObjectName(name)
        : current.slug,
    }))
  }

  function updateObjectType(objectType: BusinessObjectType) {
    setValues((current) => ({
      ...current,
      objectType,
      payloadJson: '{\n  \n}',
      fieldValues: emptyStructuredFieldValues(objectType),
      preservedPayload: {},
      citations: [],
    }))
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editor) return
    setSubmitting(true)
    setFormError(null)
    try {
      const payload = hasStructuredBusinessFields(values.objectType)
        ? encodeStructuredPayload(values.objectType, values.fieldValues, values.preservedPayload)
        : parseJsonPayload(values.payloadJson, t('businessTruth.payloadObjectRequired'))
      const shared = {
        name: values.name.trim(),
        status: values.status,
        locale: values.locale,
        payload,
        businessPurpose: values.businessPurpose.trim(),
        changeSummary: values.changeSummary.trim(),
        sourceType: 'owner_edit' as const,
        sourceRef: null,
        inputVersions: editor.object ? { previous: editor.object.currentVersion } : {},
        citations: encodeBusinessCitations(values.citations),
      }
      const requestPayload: BusinessObjectCreateInput | BusinessObjectVersionCreateInput = editor.mode === 'create'
        ? { ...shared, objectType: values.objectType, slug: values.slug.trim() }
        : shared
      const endpoint = editor.mode === 'create'
        ? '/api/business-truth/objects'
        : `/api/business-truth/objects/${editor.object?.id}/versions`
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': editor.idempotencyKey },
        body: JSON.stringify(requestPayload),
      })
      const envelope = await responseEnvelope<BusinessTruthMutation>(response)
      setProfile((current) => current ? profileAfterMutation(current, envelope.data.object) : current)
      setSource(envelope.meta.source)
      setNotice(t(editor.mode === 'create' ? 'businessTruth.createdNotice' : 'businessTruth.versionedNotice', {
        name: envelope.data.object.version.name,
      }))
      setEditor(null)
    } catch (submitError) {
      if (submitError instanceof SyntaxError) setFormError(t('businessTruth.invalidPayload'))
      else if (submitError instanceof BusinessFieldValidationError) {
        setFormError(t(`businessTruth.fieldErrors.${submitError.code}`, { line: submitError.line ?? 0 }))
      }
      else if (submitError instanceof BusinessCitationValidationError) {
        setFormError(t(`businessTruth.fieldErrors.${submitError.code}`, { line: submitError.line }))
      }
      else if (submitError instanceof BrowserApiError) setFormError(apiErrorMessage(t, submitError))
      else setFormError(submitError instanceof Error ? submitError.message : t('businessTruth.unknownError'))
    } finally {
      setSubmitting(false)
    }
  }

  return <div className="page-stack business-truth-page">
    <section className="module-hero">
      <div><span className="eyebrow">{t(`sections.${item.sectionKey}`)} · {t('businessTruth.canonicalData')}</span><h1>{t(`pages.${item.key}.title`)}</h1><p>{t(`pages.${item.key}.description`)}</p></div>
      <button className="button button--primary" onClick={openCreate} disabled={loading || Boolean(error)}><Icon name="add" size={19} />{t('businessTruth.create')}</button>
    </section>

    {notice ? <div className="truth-notice" role="status"><Icon name="check_circle" size={19} /><span>{notice}</span><button className="icon-button" aria-label={t('businessTruth.dismiss')} onClick={() => setNotice(null)}><Icon name="close" size={18} /></button></div> : null}

    {loading ? <LoadingState label={t('businessTruth.loading')} /> : null}
    {!loading && error ? <ErrorState error={error} retry={() => void loadProfile()} /> : null}
    {!loading && !error && profile ? <>
      <section className="truth-summary">
        <article><span><Icon name="database" size={20} /></span><div><strong>{objects.length}</strong><small>{t('businessTruth.recordsInCapability')}</small></div></article>
        <article><span><Icon name="fact_check" size={20} /></span><div><strong>{profile.citationCount}</strong><small>{t('businessTruth.profileCitations')}</small></div></article>
        <article><span><Icon name={profile.validationState === 'complete' ? 'verified' : 'pending_actions'} size={20} /></span><div><strong>{t(`businessTruth.validation.${profile.validationState}`)}</strong><small>{t('businessTruth.workspaceProfile')}</small></div></article>
        <article><span><Icon name="dns" size={20} /></span><div><strong>{source ? t(`businessTruth.source.${source}`) : '—'}</strong><small>{t('businessTruth.dataSource')}</small></div></article>
      </section>

      {showRetrieval ? <section className="truth-retrieval" aria-label={t('businessTruth.retrievalTitle')}>
        <div><Icon name="search" size={19} /><input type="search" value={retrievalQuery} placeholder={t('businessTruth.retrievalPlaceholder')} aria-label={t('businessTruth.retrievalSearchLabel')} onChange={(event) => setRetrievalQuery(event.target.value)} /></div>
        <label><span>{t('businessTruth.retrievalTypeLabel')}</span><select value={retrievalType} onChange={(event) => setRetrievalType(event.target.value as BusinessObjectType | 'all')}><option value="all">{t('businessTruth.allKnowledgeTypes')}</option>{retrievalTypes.map((type) => <option value={type} key={type}>{t(`businessTruth.objectTypes.${type}`)}</option>)}</select></label>
        <small>{t('businessTruth.retrievalBoundary', { count: visibleObjects.length })}</small>
      </section> : null}

      <section className="panel">
        <div className="panel-heading"><div><h2>{t('businessTruth.records')}</h2><p>{t('businessTruth.recordsDescription')}</p></div><StatusBadge tone={source === 'live' ? 'positive' : 'neutral'}>{source ? t(`businessTruth.source.${source}`) : '—'}</StatusBadge></div>
        {visibleObjects.length ? <div className="truth-records">{visibleObjects.map((object) => <BusinessTruthCard key={object.id} object={object} allObjects={profile.objects} onVersion={() => openVersion(object)} />)}</div> : objects.length && showRetrieval ? <div className="truth-empty truth-empty--compact"><span><Icon name="search_off" size={27} /></span><h3>{t('businessTruth.noRetrievalResults')}</h3><p>{t('businessTruth.noRetrievalResultsBody')}</p></div> : <div className="truth-empty"><span><Icon name="inventory_2" size={27} /></span><h3>{t('businessTruth.emptyTitle')}</h3><p>{t('businessTruth.emptyBody')}</p><button className="button button--secondary" onClick={openCreate}><Icon name="add" size={18} />{t('businessTruth.createFirst')}</button></div>}
      </section>
    </> : null}

    {editor ? <div className="modal-backdrop" role="presentation" onMouseDown={() => !submitting && setEditor(null)}><form className="modal truth-editor" role="dialog" aria-modal="true" aria-labelledby="truth-editor-title" onSubmit={submit} onMouseDown={(event) => event.stopPropagation()}>
      <header><div><span className="eyebrow">{t(`sections.${item.sectionKey}`)}</span><h2 id="truth-editor-title">{t(editor.mode === 'create' ? 'businessTruth.createTitle' : 'businessTruth.versionTitle')}</h2></div><button className="icon-button" type="button" aria-label={t('businessTruth.close')} disabled={submitting} onClick={() => setEditor(null)}><Icon name="close" /></button></header>
      <div className="truth-editor__grid">
        <label className="field-label"><span>{t('businessTruth.objectType')}</span><select value={values.objectType} disabled={editor.mode === 'version'} onChange={(event) => updateObjectType(event.target.value as BusinessObjectType)}>{objectTypes.map((type) => <option value={type} key={type}>{t(`businessTruth.objectTypes.${type}`)}</option>)}</select></label>
        <label className="field-label"><span>{t('businessTruth.status')}</span><select value={values.status} onChange={(event) => setValues({ ...values, status: event.target.value as BusinessObjectStatus })}><option value="draft">{t('businessTruth.statuses.draft')}</option><option value="active">{t('businessTruth.statuses.active')}</option><option value="archived">{t('businessTruth.statuses.archived')}</option></select></label>
        <label className="field-label"><span>{t('businessTruth.name')}</span><input required maxLength={200} value={values.name} onChange={(event) => updateName(event.target.value)} /></label>
        <label className="field-label"><span>{t('businessTruth.slug')}</span><input required minLength={2} maxLength={120} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" disabled={editor.mode === 'version'} value={values.slug} onChange={(event) => setValues({ ...values, slug: event.target.value })} /></label>
        <label className="field-label"><span>{t('businessTruth.locale')}</span><input required minLength={2} maxLength={12} value={values.locale} onChange={(event) => setValues({ ...values, locale: event.target.value })} /></label>
      </div>
      <label className="field-label"><span>{t('businessTruth.businessPurpose')}</span><textarea required minLength={8} maxLength={240} rows={2} value={values.businessPurpose} onChange={(event) => setValues({ ...values, businessPurpose: event.target.value })} /></label>
      <label className="field-label"><span>{t('businessTruth.changeSummary')}</span><textarea required minLength={3} maxLength={500} rows={2} value={values.changeSummary} onChange={(event) => setValues({ ...values, changeSummary: event.target.value })} /></label>
      {hasStructuredBusinessFields(values.objectType)
        ? <StructuredPayloadEditor
          objectType={values.objectType}
          values={values.fieldValues}
          objects={profile?.objects ?? []}
          preservedCount={Object.keys(values.preservedPayload).length}
          onChange={(key, value) => setValues((current) => ({ ...current, fieldValues: { ...current.fieldValues, [key]: value } }))}
        />
        : <label className="field-label"><span>{t('businessTruth.payload')}</span><textarea required className="truth-json" rows={7} spellCheck={false} value={values.payloadJson} onChange={(event) => setValues({ ...values, payloadJson: event.target.value })} /><small>{t('businessTruth.payloadHelp')}</small></label>}
      {values.objectType !== 'evidence' ? <CitationEditor citations={values.citations} objects={profile?.objects ?? []} onChange={(citations) => setValues((current) => ({ ...current, citations }))} /> : null}
      {formError ? <p className="truth-form-error" role="alert"><Icon name="error" size={18} />{formError}</p> : null}
      <footer><button className="button button--secondary" type="button" disabled={submitting} onClick={() => setEditor(null)}>{t('businessTruth.cancel')}</button><button className="button button--primary" type="submit" disabled={submitting}>{submitting ? t('businessTruth.saving') : t(editor.mode === 'create' ? 'businessTruth.saveObject' : 'businessTruth.saveVersion')}</button></footer>
    </form></div> : null}
  </div>
}

function CitationEditor({ citations, objects, onChange }: {
  citations: EditableBusinessCitation[]
  objects: BusinessObject[]
  onChange: (citations: EditableBusinessCitation[]) => void
}) {
  const t = useTranslations()
  const evidence = evidenceVersionOptions(objects)
  function update(id: string, patch: Partial<EditableBusinessCitation>) {
    onChange(citations.map((citation) => citation.id === id ? { ...citation, ...patch } : citation))
  }
  return <fieldset className="truth-domain-fields truth-citation-editor">
    <legend><span>{t('businessTruth.citationsTitle')}</span><small>{t('businessTruth.citationsHelp')}</small></legend>
    {citations.length ? <div className="truth-citation-editor__rows">{citations.map((citation, index) => <article key={citation.id}>
      <header><strong>{t('businessTruth.citationNumber', { number: index + 1 })}</strong><button type="button" className="button button--text button--small" onClick={() => onChange(citations.filter((item) => item.id !== citation.id))}><Icon name="delete" size={16} />{t('businessTruth.removeCitation')}</button></header>
      <div className="truth-editor__grid">
        <label className="field-label field-label--full"><span>{t('businessTruth.citationEvidence')}</span><select required value={citation.evidenceVersionId} onChange={(event) => update(citation.id, { evidenceVersionId: event.target.value })}><option value="">{t('businessTruth.citationEvidencePlaceholder')}</option>{evidence.map((object) => <option value={object.version.id} key={object.version.id}>{object.version.name} · v{object.version.version}</option>)}</select><small>{t('businessTruth.citationEvidenceHelp')}</small></label>
        <label className="field-label field-label--full"><span>{t('businessTruth.citationClaim')}</span><textarea required rows={2} value={citation.claimText} onChange={(event) => update(citation.id, { claimText: event.target.value })} /><small>{t('businessTruth.citationClaimHelp')}</small></label>
        <label className="field-label"><span>{t('businessTruth.citationLocatorKind')}</span><select value={citation.locatorKind} onChange={(event) => update(citation.id, { locatorKind: event.target.value as CitationLocatorKind })}>{(['section', 'page', 'url', 'record', 'custom'] as const).map((kind) => <option value={kind} key={kind}>{t(`businessTruth.citationLocatorKinds.${kind}`)}</option>)}</select></label>
        <label className="field-label"><span>{t('businessTruth.citationLocator')}</span><input required type={citation.locatorKind === 'url' ? 'url' : 'text'} value={citation.locatorValue} onChange={(event) => update(citation.id, { locatorValue: event.target.value })} /><small>{citation.locatorKind === 'custom' ? t('businessTruth.citationCustomLocatorHelp') : t('businessTruth.citationLocatorHelp')}</small></label>
      </div>
    </article>)}</div> : <p className="truth-citation-editor__empty"><Icon name="format_quote" size={18} />{evidence.length ? t('businessTruth.noCitations') : t('businessTruth.noEvidenceForCitation')}</p>}
    <button className="button button--secondary button--small" type="button" disabled={!evidence.length} onClick={() => onChange([...citations, emptyBusinessCitation(crypto.randomUUID())])}><Icon name="add" size={17} />{t('businessTruth.addCitation')}</button>
  </fieldset>
}

function StructuredPayloadEditor({
  objectType,
  values,
  objects,
  preservedCount,
  onChange,
}: {
  objectType: BusinessObjectType
  values: Record<string, string>
  objects: BusinessObject[]
  preservedCount: number
  onChange: (key: string, value: string) => void
}) {
  const t = useTranslations()
  const definitions = structuredBusinessFields[objectType] ?? []
  return <fieldset className="truth-domain-fields">
    <legend><span>{t(`businessTruth.objectTypes.${objectType}`)}</span><small>{t('businessTruth.domainFieldsHelp')}</small></legend>
    <div className="truth-editor__grid">
      {definitions.map((field) => <StructuredField key={field.key} field={field} value={values[field.key] ?? ''} objects={objects} onChange={(value) => onChange(field.key, value)} />)}
    </div>
    {preservedCount ? <p className="truth-preserved-note"><Icon name="info" size={17} />{t('businessTruth.preservedAttributes', { count: preservedCount })}</p> : null}
  </fieldset>
}

function StructuredField({ field, value, objects, onChange }: {
  field: BusinessFieldDefinition
  value: string
  objects: BusinessObject[]
  onChange: (value: string) => void
}) {
  const t = useTranslations()
  const label = t(`businessTruth.fields.${field.key}.label`)
  const help = t(`businessTruth.fields.${field.key}.help`)
  const className = `field-label${field.span === 'full' ? ' field-label--full' : ''}`
  if (field.kind === 'select') return <label className={className}><span>{label}</span><select required={field.required} value={value} onChange={(event) => onChange(event.target.value)}><option value="">{t('businessTruth.selectPlaceholder')}</option>{field.options?.map((option) => <option value={option} key={option}>{t(`businessTruth.fieldOptions.${option}`)}</option>)}</select><small>{help}</small></label>
  if (field.kind === 'reference') {
    const options = referencedObjects(objects, field.referenceTypes)
    return <label className={className}><span>{label}</span><select required={field.required} value={value} onChange={(event) => onChange(event.target.value)}><option value="">{t('businessTruth.referencePlaceholder')}</option>{options.map((object) => <option value={object.id} key={object.id}>{object.version.name} · {object.slug}</option>)}</select><small>{options.length || !field.required ? help : t('businessTruth.referenceEmpty')}</small></label>
  }
  if (field.kind === 'textarea' || field.kind === 'list' || field.kind === 'priceRows' || field.kind === 'committeeRows' || field.kind === 'outcomeRows') return <label className={className}><span>{label}</span><textarea required={field.required} rows={field.kind === 'priceRows' || field.kind === 'committeeRows' || field.kind === 'outcomeRows' ? 5 : 3} value={value} placeholder={field.kind === 'priceRows' ? t('businessTruth.priceRowsPlaceholder') : field.kind === 'committeeRows' ? t('businessTruth.committeeRowsPlaceholder') : field.kind === 'outcomeRows' ? t('businessTruth.outcomeRowsPlaceholder') : undefined} onChange={(event) => onChange(event.target.value)} /><small>{help}</small></label>
  return <label className={className}><span>{label}</span><input required={field.required} type={field.kind === 'url' ? 'url' : field.kind === 'date' ? 'date' : 'text'} value={value} onChange={(event) => onChange(event.target.value)} /><small>{help}</small></label>
}

function BusinessTruthCard({ object, allObjects, onVersion }: { object: BusinessObject; allObjects: BusinessObject[]; onVersion: () => void }) {
  const t = useTranslations()
  const locale = useLocale()
  const payloadEntries = Object.entries(object.version.payload).slice(0, 4)
  const knownFields = new Map((structuredBusinessFields[object.objectType] ?? []).map((field) => [field.key, field]))
  return <article className="truth-record">
    <header><div><span className="truth-record__icon"><Icon name="data_object" size={19} /></span><div><small>{t(`businessTruth.objectTypes.${object.objectType}`)}</small><h3>{object.version.name}</h3></div></div><StatusBadge tone={object.version.status === 'active' ? 'positive' : object.version.status === 'draft' ? 'warning' : 'neutral'}>{t(`businessTruth.statuses.${object.version.status}`)}</StatusBadge></header>
    <div className="truth-record__meta"><span>{object.slug}</span><span>v{object.currentVersion}</span><span>{object.version.locale}</span><span>{new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date(object.version.createdAt))}</span></div>
    <p>{object.version.businessPurpose}</p>
    {payloadEntries.length ? <dl>{payloadEntries.map(([key, value]) => {
      const field = knownFields.get(key)
      return <div key={key}><dt>{field ? t(`businessTruth.fields.${key}.label`) : key}</dt><dd>{field?.kind === 'select' && typeof value === 'string' ? t(`businessTruth.fieldOptions.${value}`) : formatPayloadValue(value, field, allObjects)}</dd></div>
    })}</dl> : null}
    {object.version.citations.length ? <div className="truth-citations"><strong>{t('businessTruth.citationEvidenceList')}</strong>{object.version.citations.map((citation) => {
      const locator = citationLocatorParts(citation.locator)
      return <div key={citation.id}><span><Icon name="verified" size={15} />{citation.evidenceName} · v{citation.evidenceVersion}</span><p>{citation.claimText}</p><small>{t(`businessTruth.citationLocatorKinds.${locator.locatorKind}`)} · {locator.locatorValue}</small></div>
    })}</div> : null}
    <footer><span><Icon name="format_quote" size={16} />{t('businessTruth.citationCount', { count: object.version.citations.length })}</span><button className="button button--secondary button--small" onClick={onVersion}><Icon name="history" size={17} />{t('businessTruth.newVersion')}</button></footer>
  </article>
}

function LoadingState({ label }: { label: string }) {
  return <section className="panel truth-state" aria-live="polite"><span className="truth-spinner" /><p>{label}</p></section>
}

function ErrorState({ error, retry }: { error: BrowserApiError; retry: () => void }) {
  const t = useTranslations()
  return <section className="panel truth-state truth-state--error"><span><Icon name={error.status === 401 || error.status === 403 ? 'lock' : 'cloud_off'} size={27} /></span><h2>{t(error.status === 401 || error.status === 403 ? 'businessTruth.unauthorizedTitle' : 'businessTruth.unavailableTitle')}</h2><p>{apiErrorMessage(t, error)}</p><button className="button button--secondary" onClick={retry}><Icon name="refresh" size={18} />{t('businessTruth.retry')}</button></section>
}

function apiErrorMessage(t: ReturnType<typeof useTranslations>, error: BrowserApiError) {
  if (error.status === 401 || error.status === 403) return t('businessTruth.unauthorizedBody')
  if (error.status === 503) return t('businessTruth.unavailableBody')
  if (error.status === 409) return t('businessTruth.conflictBody')
  if (error.status === 422) return t('businessTruth.validationBody', { detail: error.message })
  return t('businessTruth.requestFailed', { status: error.status })
}

function formatPayloadValue(value: unknown, field?: BusinessFieldDefinition, objects: BusinessObject[] = []) {
  if (field?.kind === 'reference' && typeof value === 'string') {
    return objects.find((object) => object.id === value)?.version.name ?? value
  }
  if (field?.kind === 'priceRows' && Array.isArray(value)) {
    return value.map((entry) => {
      if (!entry || typeof entry !== 'object') return String(entry)
      const row = entry as Record<string, unknown>
      return `${row.itemReference ?? '—'} · ${row.amount ?? '—'} ${row.unit ?? ''}`.trim()
    }).join(', ')
  }
  if (field?.kind === 'committeeRows' && Array.isArray(value)) {
    return value.map((entry) => {
      if (!entry || typeof entry !== 'object') return String(entry)
      const row = entry as Record<string, unknown>
      return `${row.role ?? '—'} · ${row.influence ?? '—'} · ${row.priorities ?? '—'}`
    }).join(', ')
  }
  if (field?.kind === 'outcomeRows' && Array.isArray(value)) {
    return value.map((entry) => {
      if (!entry || typeof entry !== 'object') return String(entry)
      const row = entry as Record<string, unknown>
      return `${row.metric ?? '—'} · ${row.result ?? '—'} · ${row.period ?? '—'}`
    }).join(', ')
  }
  if (Array.isArray(value)) return value.join(', ')
  if (value && typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function parseJsonPayload(value: string, objectRequiredMessage: string) {
  const payload = JSON.parse(value) as Record<string, unknown>
  if (!payload || Array.isArray(payload) || typeof payload !== 'object') throw new Error(objectRequiredMessage)
  return payload
}
