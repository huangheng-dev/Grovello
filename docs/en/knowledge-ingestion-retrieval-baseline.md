# Enterprise Knowledge Ingestion and Grounded Retrieval implementation baseline

Status: **approved; P2-E1 implemented and locally verified through July 23, 2026; P2-E2 through P2-E4 are not implemented and no operational claim is made**.

This baseline defines the P2-E delivery boundary for turning governed enterprise knowledge into versioned, workspace-isolated, citable retrieval. It completes the retrieval part of Phase 2 shared business truth without changing the ten product domains, the primary navigation, or the formal technology baseline.

## 1. Required change alignment

| Concern | P2-E alignment |
| --- | --- |
| Objective | Convert approved knowledge sources into immutable derived chunks and return purpose-bound retrieval results with exact source-version citations. |
| Product domain | Brand & Market owns enterprise knowledge; Data & Intelligence may consume retrieval evidence; Automation Runtime provides durable workflow and model-routing contracts. |
| Shared objects | `KnowledgeDocument`, `KnowledgeChunk`, `Asset`, `Evidence`, `CaseStudy`, `Citation`, `Run`, `Task`, `ModelConfig`, `AuditEvent`. |
| Inputs | An exact active source version, locale, usage rights, sensitivity, business purpose, pipeline version, parser profile, and optional embedding model configuration. |
| Governed actions | Snapshot, extract, normalize, classify, chunk, embed, publish, retrieve, reindex, cancel, retire, and rebuild. |
| Outputs | An immutable knowledge generation, derived chunk versions, rebuildable lexical/vector projections, retrieval receipts, citations, audit events, and outbox events. |
| Feedback path | No-result, low-score, stale-source, citation-use, latency, and operator feedback inform source correction, reindexing, and later strategy quality. |
| Permissions and approval | Narrow knowledge permissions, source-object authorization, sensitivity policy, purpose binding, and approval for high-risk reindex or retirement actions. |
| Verification | RLS, migrations, parser limits, idempotency, workflow retry/cancellation/compensation, retrieval isolation, citation accuracy, injection resistance, bilingual UX, and rebuild tests. |

## 2. Product and navigation boundary

- P2-E deepens the existing **Knowledge Documents** experience under Brand & Market.
- It does not add a top-level domain or a new primary-navigation item.
- Ingestion status, source history, and a retrieval test surface may appear inside the existing knowledge route. An advanced subroute is allowed only if the page becomes too dense.
- `KnowledgeChunk` remains a derived object. Owners cannot create or edit chunks through the generic business-truth mutation API or imports.
- P2-E returns evidence and citations. It does not create marketing copy, recommendations, strategies, answers, or autonomous agent actions.
- Content & Traffic, Data & Intelligence, and later agents may consume the public retrieval contract; they must not copy private chunk stores.

## 3. Source-of-truth and projection rule

PostgreSQL remains the source of truth for source snapshots, ingestion state, active generation selection, canonical chunk identity, retrieval receipts, audit, and outbox lineage.

`KnowledgeChunk` uses the existing canonical business-object identity and an immutable pipeline-created version. The internal source type may add `pipeline`, but public owner/import schemas continue to reject both `source_type=pipeline` and owner-created `knowledge_chunk` records.

Lexical search structures and pgvector embeddings are rebuildable projections. They never become the only copy of chunk text, source locators, permission metadata, or active-generation state. OpenSearch is not introduced in P2-E.

Every chunk must resolve to:

1. one exact source object and immutable source version;
2. one ingestion generation and pipeline version;
3. a stable source locator such as section, heading, paragraph, or page;
4. a content hash, locale, usage-rights state, and sensitivity classification;
5. the parser, chunker, and embedding lineage used to produce it.

## 4. Initial delivery scope

### Included governed sources

- approved active `KnowledgeDocument` versions;
- verified or owner-attested active `Evidence` versions whose usage rights permit the requested purpose;
- approved active `CaseStudy` versions;
- exact active, clean, available Asset versions explicitly attached as knowledge sources.

Structured Brand, Product, Offer, PriceBook, Market, and ICP facts remain available through the canonical business-truth API. P2-E may filter or link them but does not duplicate them into uncontrolled private copies.

### Initial extractor policy

- Canonical `KnowledgeDocument` text is the first required source.
- UTF-8 plain text and Markdown Assets may follow through the same versioned extractor contract.
- Text-extractable PDF and DOCX support requires a pinned parser, license review, bounded decompression, fixture coverage, and explicit product-owner approval within P2-E.
- OCR, image/audio/video transcription, spreadsheets, archives, executable formats, encrypted documents, macros, remote URL fetches, and external crawling are excluded from the initial acceptance gate.
- Embedded links, scripts, attachments, and remote resources are never executed or fetched during extraction.

### Default bounded configuration

Implementation settings use the `GROVELLO_KNOWLEDGE_` namespace and must enforce positive upper bounds for:

- source bytes, extracted characters, pages, table cells, and nested document parts;
- chunks per source, target chunk size, overlap, and metadata bytes;
- query characters, requested result count, candidate count, and retrieval timeout;
- concurrent ingestion activities, parser time, model time, retry count, and retained failed generations.

Defaults must fit the local Compose profile. Operators may lower limits per workspace policy; raising hard safety ceilings requires explicit deployment configuration.

## 5. Canonical execution records

### KnowledgeIngestion

One idempotent request to process an exact source version. It records workspace, actor, purpose, source type/ID/version, requested pipeline profile, approval state, status, Temporal workflow ID/run ID, cancellation, failure classification, cost, and timestamps.

### KnowledgeSourceSnapshot

The immutable input envelope resolved before workflow execution. It records exact source and Asset version IDs, content/blob hash, locale, source status, usage rights, sensitivity, parser eligibility, and the policy version used for authorization.

### KnowledgeGeneration

One immutable output generation for a source snapshot and pipeline version. It records extractor, normalizer, classifier, chunker, embedding configuration, counts, warnings, publish state, and the exact set of chunk-version IDs. At most one generation is active for a source version and retrieval profile.

### KnowledgeChunk

A canonical, pipeline-created `knowledge_chunk` object and immutable version. Its bounded payload contains normalized text, ordinal, source locator, content hash, locale, token/character counts, topics, audiences, usage rights, sensitivity, untrusted-content flags, and exact generation/source lineage.

Chunks are never silently updated. Reprocessing publishes a new generation and retires the previous generation from retrieval while preserving history.

### KnowledgeEmbeddingProjection

A rebuildable row keyed by workspace, chunk version, model configuration/version, dimension, and content hash. The vector is valid only for that exact tuple. Dimension changes or model revisions require a new projection generation.

### RetrievalReceipt

A bounded execution record containing workspace, actor, purpose, query hash, safe normalized-query metadata, filters, policy version, lexical/vector configuration, returned chunk-version IDs, component scores, rank, latency, and timestamp. Raw queries are not copied into audit evidence by default and follow workspace retention policy when persistence is necessary.

## 6. API and service boundary

The versioned FastAPI surface is rooted at `/api/v1/knowledge`:

- `POST /ingestions` creates an idempotent ingestion request for an exact source version;
- `GET /ingestions` lists authorized bounded summaries;
- `GET /ingestions/{ingestion_id}` returns persisted progress, warnings, and failure state;
- `POST /ingestions/{ingestion_id}/cancel` requests native Temporal cancellation;
- `POST /ingestions/{ingestion_id}/retry` creates an explicit retry from a terminal recoverable state;
- `POST /sources/{source_version_id}/reindex` creates a new immutable generation;
- `POST /generations/{generation_id}/retire` removes a generation from retrieval without erasing lineage;
- `POST /retrievals` performs a bounded authorized search and returns a retrieval receipt with exact citations;
- `GET /retrievals/{receipt_id}` reads an authorized retained receipt.

The API resolves identity, authorization, source eligibility, idempotency, policy, and request lineage. It never parses a document, calls an embedding provider, or performs unbounded indexing inline.

Bounded PostgreSQL retrieval may execute synchronously after authorization. Ingestion, extraction, embedding, reindexing, retirement with fan-out, and rebuilds run through Temporal workers.

The Next.js application uses a same-origin thin BFF. Browser code never receives object-storage keys, provider credentials, unrestricted chunk exports, or development identity headers.

## 7. Durable ingestion workflow

Temporal owns a deterministic, versioned workflow:

```text
authorize exact source snapshot
→ resolve canonical text or verified Asset binding
→ extract with a versioned bounded parser
→ normalize without changing factual meaning
→ classify locale, sensitivity, and untrusted-content signals
→ create deterministic chunks and locators
→ stage immutable chunks and lexical projection outside retrieval visibility
→ request and stage embeddings through the provider-neutral Model Router contract
→ transactionally publish the active-generation pointer, audit, and outbox
→ retire the previous active projection
```

Chunk and projection writes may use bounded batches, but retrieval sees none of them until the final active-generation pointer commits. Each activity has bounded timeouts, classified errors, retry policy, heartbeats where needed, and deterministic idempotency keys. Cancellation stops new work and cleans only unpublished projections created by that ingestion. A failed publish never hides the previous active generation.

LangGraph does not orchestrate this pipeline. Later agents consume retrieval results as untrusted evidence through a bounded tool contract.

## 8. Model Router and retrieval contract

P2-E introduces only the minimum public embedding-capability contract required by the formal Model Router boundary. Domain code depends on normalized embedding requests and results, never a vendor SDK.

The contract records provider reference, model ID and revision, vector dimension, tokenizer/chunker compatibility, data-use policy, regional policy, timeout, cost, and health. Secrets remain external references.

A deterministic fake embedding may verify contracts but cannot satisfy semantic-quality acceptance. A real local or configured provider must be labeled with its license, data policy, and capability state. When no embedding provider is configured, lexical retrieval remains usable and the response explicitly reports `semantic_status=unavailable`; it must not fabricate vector scores.

Retrieval applies:

1. workspace, source-status, active-generation, locale, usage-rights, sensitivity, audience, and purpose filters;
2. PostgreSQL lexical candidates;
3. pgvector candidates only when a compatible projection is available;
4. deterministic hybrid ranking with separately exposed lexical and vector scores;
5. stable tie-breaking and a bounded result count.

Every result includes the exact chunk version, source object/version, generation, locator, safe snippet, score components, and policy decision. P2-E does not generate a natural-language answer inside retrieval.

## 9. Permissions and approval

P2-E adds narrow permissions rather than expanding `business_truth.read` or `business_truth.write`:

| Permission | Risk | Purpose |
| --- | --- | --- |
| `knowledge.retrieve` | R0 | Run bounded retrieval over sources already authorized for the actor and purpose. |
| `knowledge.ingest` | R1 | Ingest an eligible approved source version. |
| `knowledge.reindex` | R1 | Create a new generation without changing the source. |
| `knowledge.cancel` | R1 | Cancel an ingestion owned or governed by the actor. |
| `knowledge.retire` | R2 | Remove an active generation from retrieval. |
| `knowledge.sensitive.read` | R2 | Retrieve content classified above the normal workspace level. |
| `knowledge.admin` | R2 | Change approved pipeline/model profiles or start a workspace rebuild. |

Source-object authorization is always evaluated in addition to the knowledge permission. A retrieval permission never bypasses business-truth, Asset, usage-rights, regional, retention, or sensitivity policy.

Routine ingestion of an already approved source under an approved unchanged pipeline may proceed by policy. A new parser/profile, sensitivity downgrade, high-impact retirement, or bulk rebuild requires the recorded approval policy version and decision.

## 10. Security and privacy review

- Extracted content is untrusted data, never system instructions.
- Retrieval cannot execute tools, follow links, run macros, fetch remote resources, or change policy.
- Prompt-injection indicators are stored as signals; they do not automatically prove malicious intent or grant the content authority.
- Parser processes enforce file/type allowlists, byte/page/part/time limits, bounded decompression, and no network egress.
- Binary sources must already be exact, active, clean, and available under the Asset contract.
- Workspace RLS is forced on every tenant-owned ingestion, generation, projection, and receipt table.
- Queries and snippets are minimized in logs, traces, audit evidence, and error messages.
- Sensitive results require explicit authorization and are excluded from broad previews and exports.
- Chunk text, embeddings, and receipts follow source retention and deletion policy. Retirement is immediate for retrieval; physical deletion remains an audited workflow.
- Cross-tenant cache keys, vector queries, model batches, and worker activities include and verify workspace scope.
- Model providers receive only the minimum authorized text and declared metadata under an approved data-use policy.

## 11. Observability and operational evidence

Required metrics include ingestion duration, extraction failures, chunk counts, embedding cost, projection lag, retrieval latency, no-result rate, filtered-result counts, stale generations, cancellation, retries, and citation-use feedback.

Logs and traces correlate request ID, workspace, ingestion, workflow, source version, generation, model configuration, and receipt without exposing secrets or unrestricted content.

Runbooks must cover stuck ingestion, parser failure, provider outage, dimension mismatch, corrupted projection, reindex, retirement, restore, and full projection rebuild from PostgreSQL source truth.

## 12. Delivery slices

### P2-E1 — Contracts, isolation, and canonical derived identity

- migration, RLS, permissions, ingestion/generation/receipt schemas, internal pipeline-only chunk creation, API contracts, idempotency, audit, outbox, and migration parity;
- generic owner and import APIs continue to reject `knowledge_chunk` creation;
- no parsing, embedding, or semantic capability claim.

Implementation evidence: migration `0012` creates five tenant-scoped knowledge execution tables with forced RLS and seven risk-tiered permissions. The versioned API creates and reads idempotent pending ingestions only for exact eligible active source versions, while internal service actors alone may create immutable pipeline-derived chunk versions with exact source and generation lineage. Local verification covered real PostgreSQL upgrade/check/downgrade/upgrade parity, non-superuser cross-workspace RLS isolation, HTTP idempotency/conflict/authorization behavior, pipeline replay safety, generic-API concealment, and exact audit/outbox evidence.

### P2-E2 — Durable extraction and deterministic chunking

- Temporal workflow, canonical text ingestion, bounded extractor registry, normalization, classification, deterministic locators/chunks, cancellation, retry, compensation, and prior-generation safety;
- initial binary extractor support only after dependency, license, and adversarial-parser tests pass;
- no semantic-quality claim.

### P2-E3 — Provider-neutral embedding and grounded retrieval

- minimum Model Router embedding contract, pgvector projection, PostgreSQL lexical retrieval, hybrid ranking, policy filters, retrieval receipts, exact citations, provider-unavailable fallback, evaluation fixtures, and rebuild tests;
- no generated answer or agent autonomy.

### P2-E4 — Bilingual operator experience and acceptance

- ingestion status/history, warnings, retry/cancel/reindex/retire controls, retrieval test surface, citation/source inspection, responsive accessibility, and EN/zh-CN parity inside the existing knowledge experience;
- full local multi-service acceptance from an approved source through retrieval, exact citation, reindex, retirement, audit/outbox lineage, and projection rebuild.

## 13. Exit gate and non-claims

P2-E is complete only when a clean workspace can ingest an approved exact source version, publish deterministic chunks, retrieve an authorized result with an exact citation, survive retry/cancellation, replace and retire generations safely, rebuild projections, and reproduce the journey in both locales without cross-tenant leakage.

Until production identity, general approval, production runbooks, a non-development deployment, and an approved real embedding profile are verified:

- knowledge ingestion and retrieval remain `foundation`, not `operational`;
- deterministic fake embeddings remain test-only;
- semantic relevance, answer correctness, and business outcome improvement are not claimed;
- OCR, transcription, crawling, unrestricted file parsing, agent answer generation, and external provider synchronization are not claimed.

## 14. Architecture, security, and delivery review result

The proposed baseline is compatible with the current constitution:

- FastAPI owns the domain contract and PostgreSQL owns canonical state;
- Temporal owns durable ingestion and rebuild workflows;
- pgvector and lexical indexes remain rebuildable projections;
- the Model Router boundary prevents provider lock-in;
- LangGraph remains a later bounded consumer rather than the ingestion orchestrator;
- no product domain, primary navigation, or formal technology baseline changes.

No ADR is required to approve this baseline. An ADR becomes mandatory if implementation proposes a new mandatory database/search service, makes OpenSearch required, embeds a vendor SDK in domain code, changes the ten domains or primary navigation, permits uncontrolled remote extraction, or moves workflow durability from Temporal to LangGraph.
