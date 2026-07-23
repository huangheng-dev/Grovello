# Workspace Onboarding and Structured Import implementation baseline

Status: **approved; P2-D1 through P2-D4 foundations implemented and locally verified through July 23, 2026**.

This baseline defines the P2-D delivery boundary for persistent workspace onboarding and structured business-truth import. It implements Phase 2 of the product delivery roadmap without changing the ten product domains or the formal technology baseline.

## 1. Required change alignment

| Concern | Baseline |
| --- | --- |
| Objective | Let a workspace owner create, validate, review, activate, and later improve one canonical business profile, including governed bulk intake from structured files. |
| Primary product domain | Brand & Market. Organization & Governance participates only for workspace settings, membership, policy, permission, and audit. |
| Shared objects | Workspace, Brand, Product, Offer, PriceBook, Market, ICP, Evidence, KnowledgeDocument, Asset, CaseStudy, BusinessObjectVersion, Citation, Approval, Run, AuditEvent. |
| Inputs | Owner edits; UTF-8 CSV; a versioned Grovello JSON import package; exact canonical object IDs and immutable evidence-version IDs. |
| Actions | Upload, verify, scan, parse, map, normalize, validate, deduplicate, preview, approve, apply, cancel, compensate, and activate. |
| Outputs | Draft canonical objects or immutable object versions, exact citations, an import result and issue report, onboarding completeness, audit events, and transactional outbox events. |
| Feedback path | Validation gaps and import outcomes update onboarding completeness; activated business truth becomes governed input to intelligence, strategy, execution, attribution, and the next strategy cycle. |
| Permissions and approval | Import execution is separate from profile activation. Applying active versions, resolving destructive conflicts, or compensating accepted changes requires policy evaluation and elevated permission. |
| Verification | Schema and migration tests, workspace RLS tests, permission and cross-tenant tests, parser security tests, idempotency and workflow replay tests, audit/outbox tests, bilingual UI tests, and end-to-end import/compensation tests. |

## 2. Product and navigation boundary

Workspace onboarding is a journey across existing canonical capabilities, not an eleventh product domain and not a replacement for the six Brand & Market modules.

- The workspace setup experience may link to a persistent onboarding checklist and resume the last incomplete step.
- Brand & Market may expose an **Imports** operational subroute and contextual **Import** actions from relevant pages after the capability is implemented.
- User-facing English uses **Business Setup** for this profile journey and **Imports** for its intake workspace. Simplified Chinese uses **企业资料配置** and **数据导入**. The technical term Workspace Onboarding must not be confused with post-sale **Onboarding & Success / 客户入驻与成功** in Customer Growth.
- Imports must not become a new top-level domain or a disconnected data administration product.
- Future generic ingestion observability and cross-domain import/export governance may live in Data & Intelligence, but it does not own or duplicate Brand & Market business truth.
- The primary navigation remains unchanged for P2-D. A route is not exposed as active until its end-to-end contract, failure states, permissions, and bilingual experience pass verification.
- The same onboarding and import contracts must work for another B2B product, service, software offer, origin country, and destination market without changing the canonical model.

## 3. Source-of-truth rule

An import job is a governed ingestion and change-planning record. It is never a competing store for brand, product, offer, price, market, ICP, evidence, knowledge, asset, or case data.

Accepted rows call the same FastAPI application services used by owner edits and create canonical `BusinessObject` identities plus immutable `BusinessObjectVersion` records with `source_type=import`. Every version retains the import job, mapping version, source checksum, actor, business purpose, idempotency key, input versions, and exact citation lineage.

PostgreSQL remains the transactional source of truth. Object storage holds private source files and generated reports under bounded retention. Temporal history, caches, previews, and staging rows are execution state and can never replace canonical records.

## 4. Initial delivery scope

### Included object types

The first implementation slice accepts:

- brand, product, offer, price book, market, and ICP records;
- evidence, knowledge document, and case-study records;
- references to existing canonical assets and exact evidence versions.

Asset binaries continue through the Asset Library upload, verification, scanning, finalization, and permission contracts. P2-D does not create a second binary-upload path. Knowledge chunks remain derived pipeline objects and are not owner-importable.

### Included source formats

- UTF-8 CSV with an explicit delimiter and header row;
- a versioned Grovello JSON import package whose manifest declares schema version, locale, object type, and record count.

XLSX, external URLs, provider drives, archives, macros, embedded files, and remote synchronization are outside the first implementation slice. XLSX may be added later through a parser adapter after dependency, license, security, and resource-limit review; it must produce the same normalized staging contract.

### Default resource limits

Defaults are deployment-configurable through the `GROVELLO_IMPORT_` namespace and are enforced by the API and workers:

- 25 MiB source file;
- 10,000 records per job;
- 100 columns per CSV record;
- 64 KiB per scalar value;
- JSON nesting depth of 12;
- one active apply workflow per workspace, with a bounded configurable validation concurrency.

Increasing these limits requires load evidence, timeout and memory review, and an updated runbook. HTTP requests never parse or apply bulk data inline.

## 5. Canonical execution records

All tenant-owned records include `workspace_id`, timestamps, actor and request lineage, and workspace RLS.

### WorkspaceOnboarding

One persistent onboarding record per workspace tracks `draft`, `in_progress`, `ready_for_review`, `active`, or `blocked`; the required object types; validation gaps; policy version; last completed step; activation version; and activation actor/time. It stores completion evidence, not private copies of business data.

### ImportJob

The job records business purpose, source format and checksum, object type, parser and schema versions, selected mapping version, status, row counts, dry-run plan hash, Temporal workflow/run IDs, idempotency keys, retention deadline, cancellation/compensation state, and a redacted result summary.

Job states are:

```text
created -> uploading -> verifying -> scanning -> mapping -> validating
-> ready_for_review -> applying -> completed | partially_completed
```

Terminal and recovery states are `failed`, `cancelled`, `expired`, `compensating`, and `compensated`. Retrying resumes from persisted state; it does not create a second logical job.

### ImportSource

The source record binds one job to the exact private object-storage key and provider version, declared and verified byte length/type/checksum, scan result, encryption state, and deletion deadline. It reuses the provider-neutral storage, verification, and malware-scanning adapters already used by the Asset pipeline, but it does not create a canonical Asset or a second business-data store. Storage identifiers are internal and never returned to browser clients.

### ImportMappingVersion

Mappings are immutable once used. A version records source-column selectors, target fields, deterministic transforms, locale and type coercion, default values, reference-resolution rules, creator, and a schema fingerprint. Secrets, executable expressions, network calls, and arbitrary code are forbidden.

### ImportRow and ImportIssue

Staging rows retain a bounded normalized representation, source row number, content hash, target identity, validation state, planned operation, applied object/version IDs, and error codes. Issues contain safe field locators and redacted messages rather than unrestricted source cells.

Row states are `pending`, `valid`, `invalid`, `duplicate`, `conflict`, `planned`, `applied`, `skipped`, `failed`, and `compensated`.

### ImportChangeSet

The immutable dry-run plan records each create, new-version, skip, or conflict decision and the exact expected current version. Apply is rejected or re-planned if canonical inputs changed after review. The change set is the unit of approval, audit, cancellation, and compensation.

## 6. API and service boundary

FastAPI owns the versioned business contracts and authorization. Next.js provides only localized interaction, session context, and a thin same-origin BFF.

The planned API groups are:

```text
/api/v1/workspace-onboarding
/api/v1/workspace-onboarding/activate
/api/v1/import-jobs
/api/v1/import-jobs/{job_id}/source-upload
/api/v1/import-jobs/{job_id}/mapping
/api/v1/import-jobs/{job_id}/validation
/api/v1/import-jobs/{job_id}/change-set
/api/v1/import-jobs/{job_id}/change-set/approval
/api/v1/import-jobs/{job_id}/apply
/api/v1/import-jobs/{job_id}/cancel
/api/v1/import-jobs/{job_id}/compensate
```

Every mutation requires an `Idempotency-Key`, business purpose, authorized workspace context, and optimistic input version where relevant. List and detail responses never expose object-storage keys, credentials, unrestricted source rows, or data from another workspace.

## 7. Durable workflow

Temporal owns the long-running import lifecycle:

1. Authorize job creation and issue a constrained, private source-upload grant.
2. Verify the exact object version, expected length, declared type, and SHA-256.
3. Reuse the provider-neutral malware-scanner contract before parsing.
4. Parse with hard byte, row, column, value, nesting, time, and memory limits.
5. Normalize through the selected immutable mapping version.
6. Validate required fields, structured payload rules, canonical references, citations, and workspace ownership.
7. Build an exact-match deduplication result and immutable dry-run change set.
8. Wait for required human or policy approval without holding an HTTP request.
9. Apply in bounded transactional batches through the business-truth application service.
10. Write audit and transactional outbox records in the same transaction as each accepted canonical version.
11. Produce a redacted result report, update onboarding completeness, and remove transient source/staging data according to retention policy.

Activities have bounded timeouts, classified retry policies, heartbeats, and explicit cancellation points. Workflow inputs contain IDs, versions, hashes, and safe summaries rather than complete source files or secrets. LangGraph is not used for deterministic parsing, validation, deduplication, or apply. A future mapping suggestion may use LangGraph only as a reviewable assistant; it can never silently accept a mapping or merge.

## 8. Validation and deduplication

Validation is deterministic and versioned. It reuses the canonical business-truth validators and adds import-specific shape, reference, limit, and mapping checks.

Deduplication order is fixed:

1. explicit canonical object ID, constrained to the current workspace and matching object type;
2. exact normalized `(workspace_id, object_type, slug)` identity;
3. object-specific stable identifiers only after their schema formally defines them, such as a product SKU or market ISO code;
4. otherwise create a conflict for owner resolution.

Fuzzy, semantic, or model-proposed matches never auto-merge. A conflicting current version, missing reference, ambiguous match, or cross-workspace ID fails closed. Duplicate rows inside one file resolve deterministically and remain visible in the report.

## 9. Apply, rollback, and compensation

Imports do not overwrite mutable business truth. They create new draft objects or immutable versions. The operation key is derived from `(workspace_id, import_job_id, source_row_id, change_set_version)` so workflow retries cannot duplicate accepted versions.

There is no false promise of a single database rollback across a long-running workflow. Before apply, cancellation has no canonical effect. During apply, each bounded batch commits atomically. If a later batch fails, the job becomes `partially_completed` and exposes exact accepted and failed rows.

Compensation is policy-governed and auditable:

- a newly created, still-draft, unreferenced object may be archived or removed under the approved retention policy;
- an imported version that has become active or gained downstream references is corrected by a new version or archive transition, never by rewriting history;
- compensation verifies the expected current version and stops on concurrent owner edits;
- audit events, citations, and immutable version lineage are retained.

## 10. Permissions and approval

P2-D introduces narrow permissions rather than treating `business_truth.write` as unlimited bulk authority:

- `workspace.onboarding.read`, `workspace.onboarding.write`, `workspace.onboarding.activate`;
- `business_truth.import.read`, `business_truth.import.create`, `business_truth.import.map`, `business_truth.import.apply`, `business_truth.import.cancel`, `business_truth.import.compensate`.

Creating and validating a job is lower risk than applying it. Applying draft creates/versions additionally requires `business_truth.write`. Applying active versions or activating the profile requires policy approval and the relevant elevated permission. Compensation and conflict resolution are high-risk operations and always record actor, reason, approved change-set hash, and affected canonical versions.

The first slice rejects accounts, contacts, leads, consent, suppression, customer, commercial, and revenue records. Those require their owning domain permissions, privacy rules, and dedicated import contracts in later phases.

## 11. Security and privacy review

- The API ignores or rejects tenant, actor, status, audit, and storage identifiers supplied as ordinary source fields; trusted context supplies them.
- Private source objects use workspace-scoped keys, exact provider versions, encryption policy, malware scanning, and short-lived grants. They are never public Assets by implication.
- CSV formula prefixes are neutralized in previews and exported issue reports. No formula, macro, HTML, script, template expression, or transform code is executed.
- Parsers reject invalid encodings, duplicate or oversized headers, path traversal, archives, embedded files, excessive nesting, decompression tricks, and unsupported content types.
- URLs remain inert strings; workers do not fetch them. Untrusted content is never inserted into system prompts or tool instructions.
- Logs, traces, audit summaries, and errors exclude raw source rows and suspected secrets. Reports use stable error codes and bounded redacted samples.
- Source and staging retention defaults to 30 days after a terminal state and is policy-configurable. Audit, immutable version lineage, and required compliance evidence follow the workspace retention policy.
- Rate limits and workspace quotas cover active jobs, bytes, rows, validation work, and retained staging data. Resource exhaustion fails closed without weakening another tenant.
- Deletion honors legal hold, policy, exact object versions, and audit requirements. Operators never delete by unresolved prefix or broad workspace path.

## 12. Onboarding activation gate

Activation is explicit, versioned, and separate from import completion. The gate requires:

- the configured required canonical object types and no blocking validation gaps;
- an active or explicitly approved version for each required fact;
- valid canonical references and required exact evidence citations;
- workspace locale, time zone, currency, ownership, and baseline policy;
- an owner review of remaining warnings and the exact profile snapshot;
- `workspace.onboarding.activate` plus policy approval.

Successful activation emits `BusinessProfileActivated` with exact object-version IDs and the policy version. Reopening onboarding creates a new activation candidate; it does not mutate the earlier activation record.

## 13. Delivery slices

### P2-D1 — Contracts and isolation

Add models, migration, RLS, permissions, API schemas, storage/scan reuse contracts, idempotent job creation, status, cancellation, and tests. No business rows are applied in this slice.

Implementation evidence: migration `0008` defines all seven tenant tables with forced workspace RLS and nine risk-tiered permissions. The versioned API supports persistent onboarding creation/read and import create/list/read/complete/cancel; constrained private uploads enter a dedicated Temporal verification and malware-scanning workflow. Parsing, mapping, validation, change-set review, activation, and business-data apply remain outside P2-D1.

### P2-D2 — Mapping and validation

Add CSV and Grovello JSON adapters, immutable mappings, bounded staging, preview, deterministic validation, exact deduplication, issue reporting, and contract/security tests.

Implementation evidence: migration `0010` records the selected immutable mapping, validation
idempotency, parser version, and dedicated Temporal workflow lineage without altering canonical
business truth. The worker accepts only bounded UTF-8 CSV with an explicit allowed delimiter or a
versioned Grovello JSON package whose manifest matches the authorized job. It rejects malformed or
duplicate schemas, excessive rows, columns, scalar values, and nesting; runs only allowlisted
deterministic transforms; reuses canonical payload and workspace-reference validation; and stages
content hashes, exact identity results, formula-neutralized previews, and redacted stable-code issues.
Canonical IDs, exact normalized slugs, product SKU, and market country code are the only implemented
matching signals. Conflicting signals and fuzzy similarities never auto-merge. P2-D2 creates no
change set, canonical object, object version, activation, or apply side effect.

### P2-D3 — Apply and onboarding activation

Add dry-run change sets, policy/approval handoff, Temporal apply/cancellation/compensation, business-truth writes, profile completeness, activation, audit/outbox lineage, and recovery tests.

Implementation evidence: migration `0011` adds tenant-scoped immutable change-set operations, exact expected/result version lineage, apply and compensation workflow identifiers, approval decision idempotency, and activation snapshots. The versioned API creates and reads dry-run plans, records policy-versioned approval decisions, starts authorized apply and compensation workflows, cancels active apply through native Temporal cancellation, and activates only a complete active profile. Apply reuses the canonical business-truth service with an operation key derived from workspace, job, source row, and change-set version. Compensation creates corrective or archived immutable versions and stops on a concurrent owner version. `BusinessProfileActivated` carries the exact object-version IDs and policy version. PostgreSQL upgrade/downgrade/upgrade, forced RLS, Alembic metadata parity, permission, workflow retry, and recovery contracts are verified. P2-D3 remains `foundation` until the P2-D4 bilingual operator journey and a full local multi-service acceptance run are complete.

### P2-D4 — Bilingual operator experience

Add the localized onboarding checklist and import workspace through the thin BFF, including loading, empty, partial, failed, unauthorized, approval, retry, cancellation, compensation, mobile, keyboard, and screen-reader states. Complete a real local end-to-end run against PostgreSQL, Temporal, S3-compatible storage, and the malware scanner.

Implementation evidence: the advanced, non-primary Brand & Market routes `/brand/business-setup` and `/brand/imports` now provide English and Simplified Chinese operator journeys through a server-side BFF without changing the six primary navigation entries. The UI connects persistent onboarding, constrained browser upload, durable status polling, immutable mapping, deterministic validation evidence, change-set review, approval/apply actions, cancellation, compensation, and exact activation gating. Loading, empty, unavailable, unauthorized, conflict, blocked, completed, and compensated states are represented with responsive and accessible controls. A real browser run used PostgreSQL, Temporal, a private versioned MinIO bucket with a least-privilege application account, and ClamAV to take a CSV from upload through clean scanning, mapping, validation, change-set creation, canonical apply, and compensation. The run produced nine audit records and nine transactional outbox events. The fresh-workspace integration acceptance also passed exact activation and compensation. P2-D remains `foundation`, not `operational`, because production identity, the general approval workflow, production runbooks, and non-development deployment evidence remain outside this acceptance.

## 14. Exit gate and non-claims

P2-D is complete only when a fresh workspace can upload an allowed structured source, map and validate it, review an immutable change set, apply canonical draft facts idempotently, recover from partial failure, produce audit/outbox lineage, satisfy the onboarding gate, and activate an exact business-profile snapshot in both locales.

The local exit evidence now exists. The remaining non-claims are:

- onboarding and imports remain `planned` or `foundation`, not `operational`;
- a parser demo or uploaded file does not prove a governed import;
- import completion does not imply profile activation;
- no external drive, provider sync, XLSX, AI auto-mapping, fuzzy merge, customer-data import, or production identity capability is claimed.

## 15. Architecture, security, and delivery review result

The baseline conforms to the existing architecture: Next.js remains a thin BFF, FastAPI owns business truth, Temporal owns durable execution, PostgreSQL remains authoritative, object storage is private and provider-neutral, and LangGraph is excluded from deterministic decisions. It does not change the ten domains or introduce a provider dependency. No ADR is required for this baseline.

Implementation must stop for an ADR and product-owner approval if it proposes a new source of business truth, a new top-level domain, executable user mappings, model-controlled merge/apply, an unscanned source path, or a change to the formal technology baseline.
