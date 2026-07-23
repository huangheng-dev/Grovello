'use client'

import type {
  BusinessProfile,
  ImportableBusinessObjectType,
  WorkspaceOnboarding,
  WorkspaceOnboardingMutation,
} from '@grovello/api-client'
import type { NavigationItem } from '@grovello/product-config'
import { Icon, StatusBadge } from '@grovello/ui'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  defaultRequiredObjectTypes,
  importableObjectTypes,
  onboardingCompletedTypes,
  onboardingProgress,
  OperatorApiError,
  operatorEnvelope,
} from './onboarding-import-model'

type LocatedNavigationItem = NavigationItem & { sectionKey: string; sectionSlug: string }

const objectRoutes: Record<ImportableBusinessObjectType, string> = {
  brand: 'business-brand',
  product: 'products-offers',
  offer: 'products-offers',
  price_book: 'products-offers',
  market: 'markets',
  icp: 'ideal-customers',
  evidence: 'knowledge-evidence',
  knowledge_document: 'knowledge-evidence',
  case_study: 'knowledge-evidence',
}

export function BusinessSetupView({ item }: { item: LocatedNavigationItem }) {
  const t = useTranslations()
  const locale = useLocale()
  const [onboarding, setOnboarding] = useState<WorkspaceOnboarding | null>(null)
  const [profile, setProfile] = useState<BusinessProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<OperatorApiError | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [purpose, setPurpose] = useState('')
  const [requiredTypes, setRequiredTypes] = useState<ImportableBusinessObjectType[]>(
    defaultRequiredObjectTypes,
  )
  const [policyVersion, setPolicyVersion] = useState('1')
  const [activationPurpose, setActivationPurpose] = useState('')

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const [profileResponse, onboardingResponse] = await Promise.all([
        fetch('/api/business-truth/profile', { cache: 'no-store', signal }),
        fetch('/api/onboarding', { cache: 'no-store', signal }),
      ])
      const profileEnvelope = await operatorEnvelope<BusinessProfile>(profileResponse)
      setProfile(profileEnvelope.data)
      if (onboardingResponse.status === 404) {
        setOnboarding(null)
      } else {
        setOnboarding((await operatorEnvelope<WorkspaceOnboarding>(onboardingResponse)).data)
      }
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === 'AbortError') return
      setError(loadError instanceof OperatorApiError
        ? loadError
        : new OperatorApiError(503, String(loadError)))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const frame = requestAnimationFrame(() => void load(controller.signal))
    return () => {
      cancelAnimationFrame(frame)
      controller.abort()
    }
  }, [load])

  const completed = useMemo(
    () => onboarding && profile ? new Set(onboardingCompletedTypes(onboarding, profile)) : new Set(),
    [onboarding, profile],
  )
  const progress = onboarding && profile ? onboardingProgress(onboarding, profile) : 0
  const canActivate = Boolean(
    onboarding
    && onboarding.status !== 'active'
    && activationPurpose.trim().length >= 8
    && Number(policyVersion) >= 1,
  )

  async function startSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setFormError(null)
    try {
      const response = await fetch('/api/onboarding', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': crypto.randomUUID(),
        },
        body: JSON.stringify({
          businessPurpose: purpose.trim(),
          requiredObjectTypes: requiredTypes,
          inputVersions: { operatorExperience: 'p2-d4-v1' },
        }),
      })
      const envelope = await operatorEnvelope<WorkspaceOnboardingMutation>(response)
      setOnboarding(envelope.data.onboarding)
      setNotice(t('onboarding.startedNotice'))
    } catch (submitError) {
      setFormError(operatorMessage(t, submitError))
    } finally {
      setSubmitting(false)
    }
  }

  async function activate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setFormError(null)
    try {
      const response = await fetch('/api/onboarding/activate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': crypto.randomUUID(),
        },
        body: JSON.stringify({
          businessPurpose: activationPurpose.trim(),
          policyVersion: Number(policyVersion),
          reviewedWarningCodes: onboarding?.validationGaps
            .map((gap) => String(gap.code ?? ''))
            .filter(Boolean),
        }),
      })
      const envelope = await operatorEnvelope<WorkspaceOnboardingMutation>(response)
      setOnboarding(envelope.data.onboarding)
      setNotice(t('onboarding.activatedNotice'))
    } catch (activationError) {
      setFormError(operatorMessage(t, activationError))
      if (activationError instanceof OperatorApiError && activationError.status === 409) {
        await load()
      }
    } finally {
      setSubmitting(false)
    }
  }

  function toggleRequired(type: ImportableBusinessObjectType) {
    setRequiredTypes((current) => current.includes(type)
      ? current.filter((itemType) => itemType !== type)
      : [...current, type])
  }

  return <div className="page-stack setup-page">
    <section className="module-hero setup-hero">
      <div>
        <span className="eyebrow">{t(`sections.${item.sectionKey}`)} · {t('onboarding.foundationLabel')}</span>
        <h1>{t(`pages.${item.key}.title`)}</h1>
        <p>{t(`pages.${item.key}.description`)}</p>
      </div>
      <Link className="button button--secondary" href={`/${locale}/brand/imports`}>
        <Icon name="upload_file" size={19} />{t('onboarding.openImports')}
      </Link>
    </section>

    {notice ? <div className="truth-notice" role="status">
      <Icon name="check_circle" size={19} /><span>{notice}</span>
      <button className="icon-button" aria-label={t('common.closeMenu')} onClick={() => setNotice(null)}>
        <Icon name="close" size={18} />
      </button>
    </div> : null}

    {loading ? <SetupState icon="progress_activity" title={t('onboarding.loading')} body={t('onboarding.loadingBody')} spinning /> : null}
    {!loading && error ? <SetupState
      icon={error.status === 401 || error.status === 403 ? 'lock' : 'cloud_off'}
      title={t(error.status === 401 || error.status === 403 ? 'onboarding.unauthorizedTitle' : 'onboarding.unavailableTitle')}
      body={operatorMessage(t, error)}
      action={<button className="button button--secondary" onClick={() => void load()}><Icon name="refresh" size={18} />{t('onboarding.retry')}</button>}
    /> : null}

    {!loading && !error && !onboarding ? <section className="panel setup-empty">
      <div className="setup-empty__copy">
        <span><Icon name="checklist" size={30} /></span>
        <div><h2>{t('onboarding.emptyTitle')}</h2><p>{t('onboarding.emptyBody')}</p></div>
      </div>
      <form className="setup-start-form" onSubmit={startSetup}>
        <label className="field-label">
          <span>{t('onboarding.businessPurpose')}</span>
          <textarea required minLength={8} maxLength={240} rows={2} value={purpose} onChange={(event) => setPurpose(event.target.value)} />
        </label>
        <fieldset>
          <legend>{t('onboarding.requiredFacts')}</legend>
          <div className="setup-type-grid">
            {importableObjectTypes.map((type) => <label key={type}>
              <input type="checkbox" checked={requiredTypes.includes(type)} onChange={() => toggleRequired(type)} />
              <span>{t(`businessTruth.objectTypes.${type}`)}</span>
            </label>)}
          </div>
        </fieldset>
        {formError ? <p className="truth-form-error" role="alert"><Icon name="error" size={18} />{formError}</p> : null}
        <button className="button button--primary" disabled={submitting || requiredTypes.length === 0}>
          <Icon name="play_arrow" size={18} />{submitting ? t('onboarding.starting') : t('onboarding.start')}
        </button>
      </form>
    </section> : null}

    {!loading && !error && onboarding && profile ? <>
      <section className="setup-summary">
        <article><span><Icon name="fact_check" size={20} /></span><div><strong>{progress}%</strong><small>{t('onboarding.completeness')}</small></div></article>
        <article><span><Icon name="database" size={20} /></span><div><strong>{completed.size}/{onboarding.requiredObjectTypes.length}</strong><small>{t('onboarding.requiredFacts')}</small></div></article>
        <article><span><Icon name="warning" size={20} /></span><div><strong>{onboarding.validationGaps.length}</strong><small>{t('onboarding.blockingGaps')}</small></div></article>
        <article><span><Icon name="policy" size={20} /></span><div><strong>{onboarding.policyVersion ?? '—'}</strong><small>{t('onboarding.policyVersion')}</small></div></article>
      </section>

      <section className="panel setup-progress-panel">
        <div className="panel-heading">
          <div><h2>{t('onboarding.checklistTitle')}</h2><p>{t('onboarding.checklistBody')}</p></div>
          <StatusBadge tone={onboarding.status === 'active' ? 'positive' : 'warning'}>
            {t(`onboarding.statuses.${onboarding.status}`)}
          </StatusBadge>
        </div>
        <div className="setup-progress" role="progressbar" aria-label={t('onboarding.completeness')} aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="setup-checklist">
          {onboarding.requiredObjectTypes.map((type) => {
            const done = completed.has(type)
            return <article key={type} className={done ? 'is-complete' : ''}>
              <span><Icon name={done ? 'check_circle' : 'radio_button_unchecked'} size={22} /></span>
              <div><h3>{t(`businessTruth.objectTypes.${type}`)}</h3><p>{t(done ? 'onboarding.factComplete' : 'onboarding.factMissing')}</p></div>
              <Link className="button button--text button--small" href={`/${locale}/brand/${objectRoutes[type]}`}>
                {t(done ? 'onboarding.reviewFact' : 'onboarding.addFact')}<Icon name="arrow_forward" size={16} />
              </Link>
            </article>
          })}
        </div>
      </section>

      <div className="setup-columns">
        <section className="panel">
          <div className="panel-heading"><div><h2>{t('onboarding.gapsTitle')}</h2><p>{t('onboarding.gapsBody')}</p></div></div>
          {onboarding.validationGaps.length ? <div className="setup-gaps">
            {onboarding.validationGaps.map((gap, index) => <article key={`${String(gap.code)}-${index}`}>
              <Icon name="error" size={19} />
              <div><strong>{String(gap.code ?? t('onboarding.unknownGap'))}</strong><p>{String(gap.message ?? t('onboarding.gapFallback'))}</p></div>
            </article>)}
          </div> : <div className="setup-ready"><Icon name="verified" size={24} /><div><strong>{t('onboarding.noGaps')}</strong><p>{t('onboarding.noGapsBody')}</p></div></div>}
        </section>

        <section className="panel">
          <div className="panel-heading"><div><h2>{t('onboarding.activationTitle')}</h2><p>{t('onboarding.activationBody')}</p></div></div>
          {onboarding.status === 'active' ? <div className="setup-active">
            <Icon name="verified_user" size={28} />
            <div><strong>{t('onboarding.activeTitle')}</strong><p>{t('onboarding.activeBody', { version: onboarding.activationVersion })}</p></div>
          </div> : <form className="setup-activation-form" onSubmit={activate}>
            <label className="field-label"><span>{t('onboarding.policyVersion')}</span><input required min={1} type="number" value={policyVersion} onChange={(event) => setPolicyVersion(event.target.value)} /></label>
            <label className="field-label"><span>{t('onboarding.activationPurpose')}</span><textarea required minLength={8} maxLength={240} rows={2} value={activationPurpose} onChange={(event) => setActivationPurpose(event.target.value)} /></label>
            <p className="asset-approval-note"><Icon name="info" size={17} />{t('onboarding.activationBlocked')}</p>
            {formError ? <p className="truth-form-error" role="alert"><Icon name="error" size={18} />{formError}</p> : null}
            <button className="button button--primary" disabled={!canActivate || submitting}>
              <Icon name="verified_user" size={18} />{submitting ? t('onboarding.activating') : t('onboarding.activate')}
            </button>
          </form>}
        </section>
      </div>
    </> : null}
  </div>
}

function SetupState({ icon, title, body, action, spinning = false }: {
  icon: string
  title: string
  body: string
  action?: ReactNode
  spinning?: boolean
}) {
  return <section className="panel truth-state" aria-live="polite">
    <span className={spinning ? 'truth-spinner' : undefined}>{spinning ? null : <Icon name={icon} size={28} />}</span>
    <h2>{title}</h2><p>{body}</p>{action}
  </section>
}

function operatorMessage(t: ReturnType<typeof useTranslations>, error: unknown) {
  if (error instanceof OperatorApiError) {
    if (error.status === 401 || error.status === 403) return t('onboarding.unauthorizedBody')
    if (error.status === 409) return t('onboarding.conflictBody')
    if (error.status === 422) return t('onboarding.validationBody', { detail: error.message })
    if (error.status === 503) return t('onboarding.unavailableBody')
    return t('onboarding.requestFailed', { status: error.status })
  }
  return error instanceof Error ? error.message : t('onboarding.unknownError')
}
