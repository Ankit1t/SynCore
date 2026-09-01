/**
 * Reconciliation Worker (Blueprint 5.2, 8.1, W6).
 *
 * UNKNOWN is normal, not exceptional. This worker owns the promotion of an
 * UNKNOWN transaction to SETTLED or DROPPED by cross-checking the provider's
 * ground-truth status. It NEVER executes a payment and never makes an agent
 * judgment call — it only promotes based on evidence.
 */

import { type Clock, systemClock } from "../domain/clock.ts";
import type { AuditLedger } from "../ledger/audit.ts";
import type { SpendLedger } from "../store/memory.ts";
import { transition } from "../statemachine/payment.ts";
import type { BrokerOrchestrator } from "../broker/orchestrator.ts";
import type { ProviderAdapter } from "../broker/provider.ts";
import type { PaymentState } from "../domain/types.ts";

export interface ReconResult {
  intent_id: string;
  outcome: "SETTLED" | "DROPPED" | "NOOP";
  state: PaymentState;
}

export class ReconciliationWorker {
  #broker: BrokerOrchestrator;
  #provider: ProviderAdapter;
  #audit: AuditLedger;
  #spend: SpendLedger;
  #clock: Clock;

  constructor(
    broker: BrokerOrchestrator,
    provider: ProviderAdapter,
    audit: AuditLedger,
    spend: SpendLedger,
    clock: Clock = systemClock,
  ) {
    this.#broker = broker;
    this.#provider = provider;
    this.#audit = audit;
    this.#spend = spend;
    this.#clock = clock;
  }

  reconcile(intentId: string): ReconResult {
    const tx = this.#broker.getTransaction(intentId);
    if (!tx) return { intent_id: intentId, outcome: "NOOP", state: "DROPPED" };
    if (tx.state !== "UNKNOWN") {
      return { intent_id: intentId, outcome: "NOOP", state: tx.state };
    }

    const status = tx.provider_ref ? this.#provider.status(tx.provider_ref) : "NOT_FOUND";

    if (status === "SUCCESS") {
      tx.state = transition(tx.state, "RECON_SETTLED");
      this.#spend.record(tx.delegation_id, tx.amount_paise, this.#clock());
      this.#audit.append("recon", "PAYMENT_SETTLED", intentId, { via: "reconcile", provider_ref: tx.provider_ref });
      return { intent_id: intentId, outcome: "SETTLED", state: tx.state };
    }

    // FAILED / NOT_FOUND / still-UNKNOWN => no money moved that we can prove -> DROP.
    tx.state = transition(tx.state, "RECON_DROPPED");
    this.#audit.append("recon", "PAYMENT_DROPPED", intentId, { via: "reconcile", provider_status: status });
    return { intent_id: intentId, outcome: "DROPPED", state: tx.state };
  }
}
