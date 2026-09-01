/**
 * Broker Orchestrator (Blueprint 5.2, 8.1).
 *
 * The ONLY component that executes financial calls (rule B2). It drives the
 * payment state machine, enforces the idempotency triad's application layer
 * (unique broker idempotency key), and NEVER executes on a non-ALLOW decision
 * (fail closed). On provider timeout it parks the transaction in UNKNOWN for
 * the reconciliation worker — it never blindly retries.
 */

import { type Clock, systemClock } from "../domain/clock.ts";
import type { AuditLedger } from "../ledger/audit.ts";
import type { SpendLedger } from "../store/memory.ts";
import { transition } from "../statemachine/payment.ts";
import type { BoundTransaction, CanPayDecision, PaymentResult, PaymentState } from "../domain/types.ts";
import type { ProviderAdapter } from "./provider.ts";

export interface TransactionRecord {
  intent_id: string;
  delegation_id: string;
  amount_paise: number;
  merchant: string;
  broker_idem_key: string;
  provider: string;
  provider_ref: string | null;
  state: PaymentState;
}

export class BrokerOrchestrator {
  #txByIntent = new Map<string, TransactionRecord>();
  #txByIdemKey = new Map<string, string>(); // broker_idem_key -> intent_id
  #provider: ProviderAdapter;
  #audit: AuditLedger;
  #spend: SpendLedger;
  #clock: Clock;

  constructor(provider: ProviderAdapter, audit: AuditLedger, spend: SpendLedger, clock: Clock = systemClock) {
    this.#provider = provider;
    this.#audit = audit;
    this.#spend = spend;
    this.#clock = clock;
  }

  getTransaction(intentId: string): TransactionRecord | undefined {
    return this.#txByIntent.get(intentId);
  }

  execute(bound: BoundTransaction, decision: CanPayDecision): PaymentResult {
    // B5 / D5: never execute unless the deterministic gate said ALLOW.
    if (decision.decision !== "ALLOW") {
      return this.#result(bound, "DROPPED", null, `not executed: decision ${decision.decision}`);
    }

    const idemKey = `${bound.intent_id}:${bound.nonce}`;

    // Application-layer idempotency: a repeated key returns the existing tx.
    const existingIntent = this.#txByIdemKey.get(idemKey);
    if (existingIntent) {
      const tx = this.#txByIntent.get(existingIntent)!;
      return this.#result(bound, tx.state, tx.provider_ref, "idempotent replay");
    }

    const tx: TransactionRecord = {
      intent_id: bound.intent_id,
      delegation_id: bound.delegation_id,
      amount_paise: bound.amount_paise,
      merchant: bound.merchant,
      broker_idem_key: idemKey,
      provider: this.#provider.name,
      provider_ref: null,
      state: "PENDING",
    };
    this.#txByIntent.set(tx.intent_id, tx);
    this.#txByIdemKey.set(idemKey, tx.intent_id);
    this.#audit.append("broker", "PAYMENT_PENDING", tx.intent_id, { idemKey, amount: tx.amount_paise });

    this.#advance(tx, "EXECUTE");

    const outcome = this.#provider.execute({
      idempotency_key: idemKey,
      amount_paise: bound.amount_paise,
      currency: bound.currency,
      merchant: bound.merchant,
      bound_ref: bound.cart_hash,
    });
    tx.provider_ref = outcome.provider_ref;

    if (outcome.result === "SUCCESS") {
      this.#advance(tx, "PROVIDER_SUCCESS");
      this.#advance(tx, "FINALIZE"); // SUCCESS -> SETTLED
      this.#spend.record(tx.delegation_id, tx.amount_paise, this.#clock());
    } else if (outcome.result === "FAILED") {
      this.#advance(tx, "PROVIDER_FAILED"); // terminal, no retry ever
    } else {
      this.#advance(tx, "PROVIDER_TIMEOUT"); // -> UNKNOWN, worker owns it
    }

    return this.#result(bound, tx.state, tx.provider_ref, `provider ${outcome.result}`);
  }

  #advance(tx: TransactionRecord, event: Parameters<typeof transition>[1]): void {
    const next = transition(tx.state, event);
    tx.state = next;
    this.#audit.append("broker", `PAYMENT_${next}`, tx.intent_id, {
      event,
      provider_ref: tx.provider_ref,
    });
  }

  #result(bound: BoundTransaction, state: PaymentState, ref: string | null, detail: string): PaymentResult {
    return {
      intent_id: bound.intent_id,
      state,
      provider: this.#provider.name,
      provider_ref: ref,
      amount_paise: bound.amount_paise,
      detail,
    };
  }
}
