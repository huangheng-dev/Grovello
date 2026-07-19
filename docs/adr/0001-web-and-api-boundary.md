# ADR 0001: Next.js product surface and FastAPI business boundary

- Status: accepted
- Date: 2026-07-19

## Decision

Use Next.js 16/React 19 for the international product surface and FastAPI for versioned business APIs. Next.js may implement session-aware BFF endpoints but cannot become the canonical business backend.

## Rationale

One React platform supports the console, documentation, public pages, and future embedded experiences. Python keeps the AI/data ecosystem close to business services. A hard API boundary prevents duplicate truth, server-action coupling, and an untestable full-stack monolith.

## Consequences

Contracts are explicit and versioned. Authentication context crosses the boundary. Business writes, transactions, audit, and workflow starts remain in the API/application layer.
