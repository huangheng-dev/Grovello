# Changelog

All notable changes will be documented here. The project will use semantic versioning before its first public release.

## [Unreleased]

### Added

- Canonical Grovello product brand and code namespace across the repository.
- Fresh Grovello architecture and repository constitution.
- English-first Next.js console with Simplified Chinese support.
- FastAPI, durable workflow, agent, connector, data, and self-hosting foundations.
- Phase 1 organization and workspace access foundation with permission evaluation, audit lineage,
  recovery safeguards, PostgreSQL row-level security, and authorization-path tests.
- Phase 2 shared business truth foundation with canonical object IDs, immutable versions, exact
  evidence citations, profile validation, idempotent writes, audit and outbox lineage, and tenant RLS.
- Internationalized ten-domain navigation with explicit available, foundation, and reserved
  capability states, domain capability maps, and honest non-operational foundation pages.
- Phase 2 Brand & Market administration slice with a server-side BFF, canonical profile reads,
  governed object creation, immutable version updates, and explicit error and empty states.
- Localized governed forms for brand, product, offer, and price-book attributes, including canonical
  object references, typed price entries, domain validation, and lossless retention of legacy fields.
- Localized market and ideal-customer-profile forms with canonical market and product references,
  market-entry constraints, structured buying committees, qualification rules, and exclusions.
- Localized evidence and knowledge-document forms with provenance, verification, usage rights,
  governed content, loaded-record retrieval, and claims pinned to exact evidence versions.
- Localized governed case-study records with canonical business-object links, disclosure and
  authorization controls, structured outcomes, limitations, approved uses, and mandatory exact
  evidence citations for active versions.
- Bilingual in-product delivery roadmap for all fourteen dependency-ordered stages, with verified,
  foundation, current-focus, and planned states plus explicit deliverables and completion gates.
- Asset Library storage foundation with tenant-scoped upload records, immutable blob bindings,
  risk-tiered permissions, private versioned MinIO initialization, least-privilege application access,
  provider-neutral S3-compatible operations, health reporting, and real integration coverage.
- Governed upload-session APIs with idempotent creation, constrained presigned POST grants,
  authorized completion, cancellation, and status reads, plus Temporal integrity verification.
  Provider-neutral malware scanning now uses a digest-pinned ClamAV local reference, bounded retries,
  native cancellation, tenant-scoped quarantine, audit/outbox evidence, and fail-closed results.
  Clean uploads stop at `ready_to_finalize`; scanning never creates a ready asset or immutable blob.
- Governed Asset finalization through an idempotent Temporal Saga that promotes only clean uploads to
  immutable versioned blobs, transactionally creates or updates canonical Asset versions and file
  bindings, removes exact staging versions, and safely compensates failed database commits. Active
  finalization requires `asset.approve`; exact active, clean, available versions receive only bounded,
  audited private download grants.
- Localized Asset Library interface and server-side BFF for constrained browser upload, durable
  status tracking, governed finalization, canonical catalog reads, immutable version history, and
  audited secure downloads. The local MinIO profile uses configurable exact-origin browser access.
- Approved bilingual P2-D baseline and P2-D1 foundation for persistent workspace onboarding and
  structured business-truth import: seven forced-RLS tenant tables, nine risk-tiered permissions,
  idempotent versioned APIs, constrained private uploads, and a dedicated Temporal verification and
  malware-scanning workflow. Parsing, mapping, validation, change-set apply, and activation remain
  outside the P2-D1 capability claim.
- P2-D2 governed mapping and validation with bounded UTF-8 CSV and versioned Grovello JSON parsers,
  immutable mapping versions, deterministic transforms and canonical validation, exact-only
  deduplication, redacted previews and issue reports, and a dedicated Temporal validation workflow.
  This slice stages no change set and writes no canonical business object.

### Fixed

- PostgreSQL 18 Compose volume layout and asyncpg-backed Alembic execution.
- API Docker build context and migration artifact packaging.
- Canonical ORM metadata now matches the deployed schema for historical slug and subject uniqueness,
  Asset finalization JSONB payloads, and foundational run, audit, and outbox query indexes; migration
  `0009` is reversible and leaves tenant data and row-level security unchanged.
- Upload completion and cancellation now refresh server-generated timestamps before serializing
  async SQLAlchemy records, avoiding implicit asynchronous database reads.
