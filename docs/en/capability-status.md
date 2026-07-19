# Capability status

| Status | Meaning |
| --- | --- |
| Foundation | Route, product definition, shared objects, architecture boundary, and initial contract exist |
| Simulated | Demonstration uses labeled seed or mock data and does not make external claims |
| Connected | A provider account has passed contract, auth, health, policy, and sandbox tests |
| Operational | End-to-end execution, failure handling, audit, measurement, and runbook are verified |
| Experimental | Usable behind an explicit flag with known limits and evaluation criteria |
| Planned | Accepted architecture item with no production implementation claim |

Current repository status: Phase 0 is verified. Phase 1 organization and access is in foundation implementation: canonical organization, workspace, user, team, membership, role, permission, policy, session, and audit models exist; the PostgreSQL migration enables workspace RLS; and seeded access contracts verify authenticated, unauthorized, cross-tenant, audit, and recovery-plan paths. The development identity headers are disabled in production, and no OIDC provider or persistent access directory is connected yet. External channels, analytics projections, and production provider accounts are not connected. The visible console and access directory use labeled seed data.
