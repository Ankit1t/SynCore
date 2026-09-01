# Syncore Documentation

This folder documents Syncore's architecture, subsystems, and operational
concerns. Every major subsystem doc follows the same shape: **Purpose,
Architecture, Interfaces, Data flow, Failure modes, Security, Testing, Example**.

## Index

| Area | Docs |
|---|---|
| Overview | [architecture](architecture.md), [system_design](system_design.md), [data_flow](data_flow.md) |
| Agent | [agent_architecture](agent_architecture.md), [state_machine](state_machine.md), [failure_recovery](failure_recovery.md) |
| Discovery | [scraping_architecture](scraping_architecture.md), [scraping_adapters](scraping_adapters.md), [product_normalization](product_normalization.md) |
| Decisions | [ranking_engine](ranking_engine.md), [basket_optimization](basket_optimization.md), [budget_engine](budget_engine.md) |
| Money | [payment_architecture](payment_architecture.md) |
| Security | [security_architecture](security_architecture.md), [threat_model](threat_model.md), [authentication](authentication.md), [authorization](authorization.md) |
| Platform | [api_design](api_design.md), [database_schema](database_schema.md), [vector_schema](vector_schema.md), [event_schema](event_schema.md), [browser_automation](browser_automation.md) |
| Ops | [observability](observability.md), [cost_optimization](cost_optimization.md), [deployment](deployment.md) |
| Engineering | [testing_strategy](testing_strategy.md), [development_guide](development_guide.md), [contributing](contributing.md), [adr/](adr/) |

Diagrams (Mermaid) live in [`mermaid/`](mermaid/). Render them at
<https://mermaid.live> or with any Mermaid-aware Markdown viewer.

## The one-line mental model

> A **deterministic core** (money, budget, idempotency, state) wrapped by a
> **probabilistic edge** (language, semantic matching, explanations). The LLM
> advises; it never decides money.
