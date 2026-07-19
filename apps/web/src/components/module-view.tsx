'use client'

import { sharedObjectsBySection, type NavigationItem } from '@grovello/product-config'
import { Icon, StatusBadge } from '@grovello/ui'
import { useTranslations } from 'next-intl'
import { useMemo, useState } from 'react'

const activity = [
  ['activityDraft', 'activityHumanRecent', 'draft'],
  ['activityContract', 'activitySystemEarlier', 'complete'],
  ['activityProvider', 'activityHumanYesterday', 'pending'],
] as const

const lifecycleStages = [
  ['travel_explore', 'discover'], ['route', 'plan'], ['fact_check', 'approve'],
  ['rocket_launch', 'execute'], ['monitoring', 'measure'], ['model_training', 'learn'],
] as const

const activityStatusLabels = {
  draft: 'statusDraft',
  complete: 'statusComplete',
  pending: 'statusPending',
} as const

export function ModuleView({ item }: { item: NavigationItem & { sectionKey: string; sectionSlug: string } }) {
  const t = useTranslations()
  const [tab, setTab] = useState<'overview' | 'records' | 'settings'>('overview')
  const [filterOpen, setFilterOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const objects = useMemo(() => sharedObjectsBySection[item.sectionKey] ?? [], [item.sectionKey])
  return <div className="page-stack module-page">
    <section className="module-hero"><div><span className="eyebrow">{t(`sections.${item.sectionKey}`)} · {t('common.foundation')}</span><h1>{t(`pages.${item.key}.title`)}</h1><p>{t(`pages.${item.key}.description`)}</p></div><div className="button-row"><button className="button button--secondary" onClick={() => setFilterOpen(!filterOpen)}><Icon name="filter_list" size={19} />{t('module.filters')}</button><button className="button button--primary" onClick={() => setCreateOpen(true)}><Icon name="add" size={19} />{t('module.createAction')}</button></div></section>
    {filterOpen ? <section className="filter-bar"><label><span>{t('module.statusLabel')}</span><select defaultValue="all"><option value="all">{t('module.allStatuses')}</option><option>{t('module.statusDraft')}</option><option>{t('module.statusActive')}</option><option>{t('module.statusNeedsApproval')}</option></select></label><label><span>{t('module.ownerLabel')}</span><select><option>{t('module.allOwners')}</option><option>Huang Heng</option><option>{t('module.growthAgent')}</option></select></label><label><span>{t('module.periodLabel')}</span><select><option>{t('module.last30Days')}</option><option>{t('module.thisQuarter')}</option></select></label><button className="text-button" onClick={() => setFilterOpen(false)}>{t('module.clearFilters')}</button></section> : null}
    <nav className="page-tabs" aria-label={t('module.pageViews')}><button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>{t('module.overviewTab')}</button><button className={tab === 'records' ? 'active' : ''} onClick={() => setTab('records')}>{t('module.recordsTab')} <span>3</span></button><button className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>{t('module.settingsTab')}</button></nav>
    {tab === 'overview' ? <>
      <section className="readiness-grid"><Readiness icon="check_circle" tone="positive" title={t('module.defined')} body={t('module.definedBody')} status={t('module.ready')} /><Readiness icon="schema" tone="warning" title={t('module.workflow')} body={t('module.workflowBody')} status={t('common.foundation')} /><Readiness icon="link_off" tone="neutral" title={t('module.connection')} body={t('module.connectionBody')} status={t('common.notConnected')} /></section>
      <section className="panel"><div className="panel-heading"><div><h2>{t('module.lifecycle')}</h2><p>{t('module.lifecycleDescription')}</p></div><StatusBadge tone="neutral">{t('module.governedByPolicy')}</StatusBadge></div><div className="lifecycle">{lifecycleStages.map(([icon,key], index, list) => <div className="lifecycle-step" key={key}><span><Icon name={icon} size={21} /></span><strong>{t(`module.${key}`)}</strong>{index < list.length - 1 ? <Icon className="lifecycle-arrow" name="arrow_forward" size={18} /> : null}</div>)}</div></section>
      <div className="module-columns"><section className="panel"><div className="panel-heading"><div><h2>{t('module.sharedObjects')}</h2><p>{t('module.sharedObjectsDescription')}</p></div></div><div className="object-cloud">{objects.map((object) => <span key={object}><Icon name="data_object" size={17} />{object}</span>)}</div></section><section className="panel"><div className="panel-heading"><div><h2>{t('module.businessOutcome')}</h2><p>{t('module.businessOutcomeBody')}</p></div></div><div className="outcome-path"><span>{t('module.outcomeActivity')}</span><Icon name="arrow_forward" size={17} /><span>{t('module.outcomeTouchpoint')}</span><Icon name="arrow_forward" size={17} /><span>{t('module.outcomeRevenue')}</span><Icon name="arrow_forward" size={17} /><span>{t('module.outcomeLearning')}</span></div></section></div>
    </> : null}
    {tab === 'records' ? <section className="panel"><div className="panel-heading"><div><h2>{t('module.recentActivity')}</h2><p>{t('module.recordsDescription')}</p></div><StatusBadge tone="neutral">{t('common.seedData')}</StatusBadge></div><div className="table-scroll"><table><thead><tr><th><input aria-label={t('module.selectAll')} type="checkbox" /></th><th>{t('module.recordColumn')}</th><th>{t('module.actorTimeColumn')}</th><th>{t('module.statusLabel')}</th><th /></tr></thead><tbody>{activity.map(([name,meta,status]) => <tr key={name}><td><input aria-label={t('module.selectRecord', { record: t(`module.${name}`) })} type="checkbox" /></td><td><strong>{t(`module.${name}`)}</strong></td><td>{t(`module.${meta}`)}</td><td><StatusBadge tone={status === 'complete' ? 'positive' : status === 'pending' ? 'warning' : 'neutral'}>{t(`module.${activityStatusLabels[status]}`)}</StatusBadge></td><td><button className="icon-button" aria-label={t('module.moreActions')}><Icon name="more_horiz" size={20} /></button></td></tr>)}</tbody></table></div></section> : null}
    {tab === 'settings' ? <section className="panel settings-form"><div className="panel-heading"><div><h2>{t('module.settingsTitle')}</h2><p>{t('module.settingsBody')}</p></div></div><label><span>{t('module.defaultOwner')}</span><select><option>{t('module.workspaceOwner')}</option><option>{t('module.growthOperationsTeam')}</option></select></label><label><span>{t('module.approvalPolicy')}</span><select><option>{t('module.requireExternalApproval')}</option><option>{t('module.draftOnly')}</option></select></label><label className="toggle-row"><span><strong>{t('module.writeAudit')}</strong><small>{t('module.writeAuditBody')}</small></span><input defaultChecked type="checkbox" /></label><button className="button button--primary" type="button">{t('module.saveSettings')}</button></section> : null}
    {createOpen ? <div className="modal-backdrop" role="presentation" onMouseDown={() => setCreateOpen(false)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="create-title" onMouseDown={(event) => event.stopPropagation()}><header><div><span className="eyebrow">{t(`sections.${item.sectionKey}`)}</span><h2 id="create-title">{t('module.createTitle', { title: t(`pages.${item.key}.title`) })}</h2></div><button className="icon-button" aria-label={t('module.close')} onClick={() => setCreateOpen(false)}><Icon name="close" /></button></header><label className="field-label"><span>{t('module.nameLabel')}</span><input autoFocus placeholder={t('module.untitledRecord')} /></label><label className="field-label"><span>{t('module.ownerLabel')}</span><select><option>Huang Heng</option><option>{t('module.growthAgent')}</option></select></label><label className="field-label"><span>{t('module.descriptionLabel')}</span><textarea rows={4} placeholder={t('module.descriptionPlaceholder')} /></label><label className="checkbox-row"><input defaultChecked type="checkbox" />{t('module.saveDraftApproval')}</label><footer><button className="button button--secondary" onClick={() => setCreateOpen(false)}>{t('module.cancel')}</button><button className="button button--primary" onClick={() => setCreateOpen(false)}>{t('module.createDraft')}</button></footer></section></div> : null}
  </div>
}

function Readiness({ icon, tone, title, body, status }: { icon: string; tone: 'positive' | 'warning' | 'neutral'; title: string; body: string; status: string }) {
  return <article className={`readiness-card readiness-card--${tone}`}><div><span><Icon name={icon} size={21} /></span><StatusBadge tone={tone}>{status}</StatusBadge></div><h3>{title}</h3><p>{body}</p></article>
}
