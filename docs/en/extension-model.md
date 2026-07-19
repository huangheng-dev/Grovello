# Extension model

Grovello stays powerful without becoming provider-locked by exposing versioned contracts.

- **Connector:** declares capabilities, risks, configuration schema, idempotency, health, webhook support, and execution results. Secrets remain references outside model context.
- **Agent:** versioned role, input/output schema, allowed tools, model-routing policy, evaluation suite, cost limits, and human-interruption rules.
- **Workflow:** deterministic Temporal definition with versioned input/result, retries, timeouts, approval policy, cancellation, and compensation.
- **Template:** installable configuration that references public agent/workflow/connector contracts without hidden hosted dependencies.
- **Model provider:** normalized text, structured output, embeddings, image, audio, and video capability adapters with policy metadata.
- **MCP server:** an optional tool surface for agents; high-risk tools still pass Grovello authorization and workflow policy.

Third-party extensions must declare outbound hosts, permissions, data use, secret needs, side effects, reversibility, rate limits, license, and capability status. Installation never grants automatic execution authority.
