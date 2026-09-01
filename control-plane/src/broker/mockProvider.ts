/**
 * Mock PSP adapter (Phase 0 / Gate G1a — no real money, freeze D6).
 *
 * Deterministic and idempotent: a repeated idempotency key returns the SAME
 * outcome and never creates a second charge. Test code can script outcomes
 * (SUCCESS / FAILED / TIMEOUT). A TIMEOUT models the dangerous real case where
 * money may already have moved: the charge is recorded and the provider's
 * ground-truth status resolves to SUCCESS, so reconciliation promotes UNKNOWN
 * to SETTLED without ever re-executing.
 */

import { randomUUID } from "node:crypto";
import type {
  ExecuteOutcome,
  ExecuteRequest,
  ProviderAdapter,
  ProviderResult,
  ProviderStatus,
} from "./provider.ts";

interface Charge {
  provider_ref: string;
  amount_paise: number;
  idempotency_key: string;
}

export class MockProvider implements ProviderAdapter {
  readonly name = "mock-psp";
  #byKey = new Map<string, ExecuteOutcome>();
  #trueStatus = new Map<string, ProviderStatus>(); // provider_ref -> ground truth
  #charges: Charge[] = [];
  #script: ProviderResult[] = [];

  /** Queue the outcomes the next execute() calls should produce (FIFO). */
  scriptOutcomes(...results: ProviderResult[]): void {
    this.#script.push(...results);
  }

  capabilities() {
    return { autopay: true, refunds: true, sandbox: true };
  }

  execute(req: ExecuteRequest): ExecuteOutcome {
    // Idempotency: same key => same outcome, no additional charge.
    const cached = this.#byKey.get(req.idempotency_key);
    if (cached) return cached;

    const result: ProviderResult = this.#script.shift() ?? "SUCCESS";
    const ref = "prov_" + randomUUID().replace(/-/g, "").slice(0, 18);

    if (result === "SUCCESS") {
      this.#charges.push({ provider_ref: ref, amount_paise: req.amount_paise, idempotency_key: req.idempotency_key });
      this.#trueStatus.set(ref, "SUCCESS");
    } else if (result === "TIMEOUT") {
      // Ambiguous to the caller, but the money DID move on the provider side.
      this.#charges.push({ provider_ref: ref, amount_paise: req.amount_paise, idempotency_key: req.idempotency_key });
      this.#trueStatus.set(ref, "SUCCESS");
    } else {
      this.#trueStatus.set(ref, "FAILED");
    }

    const outcome: ExecuteOutcome = { result, provider_ref: ref };
    this.#byKey.set(req.idempotency_key, outcome);
    return outcome;
  }

  status(providerRef: string): ProviderStatus {
    return this.#trueStatus.get(providerRef) ?? "NOT_FOUND";
  }

  // --- test helpers ---
  totalCharges(): number {
    return this.#charges.length;
  }

  chargesForKey(key: string): number {
    return this.#charges.filter((c) => c.idempotency_key === key).length;
  }
}
