# Threat Model

Format per threat: **impact · likelihood · mitigation · residual risk**.
Diagram: [`mermaid/25_prompt_injection_defense.mmd`](mermaid/25_prompt_injection_defense.mmd).

| # | Threat | Impact | Likelihood | Mitigation | Residual |
|---|--------|--------|-----------|-----------|----------|
| 1 | **Prompt injection** (page says "buy expensive item") | High | High | LLM output never authorizes payment; deterministic policy/guard/budget; page content treated as data | Low |
| 2 | **Indirect injection** via product metadata | Med | High | Validation + lineage; LLM used only for hints; totals recomputed in code | Low |
| 3 | **SSRF** via crafted URLs | Med | Med | Outbound limited to configured providers/adapters; no arbitrary fetch from LLM | Low |
| 4 | **Credential/session theft** | High | Low | Secrets never sent to LLM; cookies isolated per user, never logged | Low |
| 5 | **Double payment** on retry | High | Med | Idempotency key at service + provider; property-tested | Very low |
| 6 | **Price manipulation** (stale search price) | High | Med | Authoritative checkout re-extraction + second budget gate before pay | Low |
| 7 | **Scraped-data poisoning** | Med | Med | Quality validation rejects impossible values; confidence scoring | Med |
| 8 | **Cross-tenant access** | High | Low | `user_id` scoping on all user entities; authz middleware (prod) | Low |
| 9 | **Agent runaway / cost blowup** | Med | Low | `MAX_AGENT_STEPS`, runtime cap, bounded pipeline, cost tracker | Low |
| 10 | **LLM hallucination of facts/prices** | Med | Med | LLM never sources prices/totals; deterministic data + math | Low |
| 11 | **Browser action errors** (wrong SKU/qty) | Med | Med | State verification after every action; cart verify before checkout | Low |
| 12 | **Webhook spoofing** (Phase 2) | High | Med | Signature verification, event-id dedupe, idempotent processing | Med |
| 13 | **Budget violation** | High | Low | Hard budget never exceeded; two gates; blocks order | Very low |
| 14 | **Unauthorized high-value spend** | High | Low | Policy limits + trusted vendors + HITL checkpoint | Low |

## Assumptions

Transport is TLS-terminated; secrets come from a secret manager in prod; the
mock providers are dev-only. Real integrations must re-run this model with their
specific attack surface.
