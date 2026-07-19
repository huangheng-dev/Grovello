# ADR 0002: Temporal workflow state and LangGraph reasoning state

- Status: accepted
- Date: 2026-07-19

## Decision

Temporal owns durable business workflow state. LangGraph owns bounded model-reasoning state inside workflow activities or explicitly controlled child executions.

## Rationale

Marketing and revenue processes wait for people, providers, schedules, retries, and compensation over hours or months. Agent graphs need flexible reasoning and tool selection. Combining both state models makes replay, cancellation, audit, and recovery ambiguous.

## Consequences

LangGraph nodes do not directly own irreversible business state. Temporal activities must be idempotent. High-risk actions wait on recorded policy/approval signals before connector execution.
