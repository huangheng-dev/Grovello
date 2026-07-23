# Contributing to Grovello

Read `AGENTS.md` before changing product behavior or architecture.

1. Keep changes aligned to one measurable business outcome and a fixed product domain.
2. Update both English and Simplified Chinese resources for user-visible behavior.
3. Use shared business objects and versioned contracts; do not create module-specific copies.
4. Add or update tests, migrations, capability status, configuration examples, and documentation.
5. Never claim that an unverified connector, model, workflow, or platform is production-ready.
6. Run type checks, tests, lint, builds, secret scanning, and relevant integration checks.

Use focused Conventional Commit messages such as `feat(geo): add citation observation contract`.

## Delivery and Git workflow

1. Establish and approve the architecture, security, contract, and delivery baseline before implementing a major milestone.
2. Deliver each independently verifiable slice on one focused branch and pull request. Do not wait for an entire multi-slice milestone when a completed slice can be reviewed, tested, and rolled back independently.
3. Keep planning-only changes separate from implementation when the plan requires approval before coding.
4. Use lowercase, descriptive branch names that identify the purpose and delivery slice, such as `feature/p2-d4-onboarding-journey`, `fix/import-cancellation`, or `docs/p3-governance-baseline`. Existing in-flight branches do not need renaming solely to adopt this convention.
5. Commit at coherent, verified checkpoints rather than on every file save or incomplete experiment.
6. Open implementation pull requests as drafts until their scoped verification passes. Merge only after required CI and review complete.
7. Use a separate acceptance change to upgrade capability status or enable a milestone when all dependent slices and exit gates have passed.
8. Keep dependency-update pull requests separate from product feature work.

## Architecture decisions

An ADR is required before changing a product boundary, core architecture, formal technology baseline, source of business truth, top-level domain, protected security policy, or other decision governed by `AGENTS.md`. Routine implementation inside an accepted baseline does not require a new ADR.

When an ADR is required, record the context, decision, alternatives, compatibility, migration, security, operability, open-source impact, and rollback plan. Implementation begins only after product-owner approval.
