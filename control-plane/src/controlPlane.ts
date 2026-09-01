/**
 * SYNCCORE Control Plane — the wired Zone 1 (Blueprint 5, 8).
 *
 * This is the "one payment door": the LLM (Zone 0) may only ever emit a typed
 * PaymentIntentProposal; it enters here, is bound, gated by CAN_PAY(), risk
 * scored, and — only on ALLOW and a consumed single-use nonce — executed
 * through the broker (Zone 2). Every step appends to the hash-chained audit
 * ledger before any side effect, producing a per-transaction proof bundle (W7).
 */

import { randomUUID } from "node:crypto";
import { type Clock, systemClock } from "./domain/clock.ts";
import { canonicalJson } from "./crypto/canonical.ts";
import { BindingService } from "./crypto/binding.ts";
import { KeyService, UserPasskey, verifySignature } from "./crypto/keys.ts";
import { AuditLedger } from "./ledger/audit.ts";
import { DelegationService, type CreateDelegationInput } from "./delegation/service.ts";
import { RiskEngine } from "./risk/engine.ts";
import { canPay, type CanPayInput } from "./policy/canPay.ts";
import { SpendLedger } from "./store/memory.ts";
import { BrokerOrchestrator } from "./broker/orchestrator.ts";
import { ReconciliationWorker } from "./recon/worker.ts";
import type { ProviderAdapter } from "./broker/provider.ts";
import { MockProvider } from "./broker/mockProvider.ts";
import type {
  AgentProof,
  BoundTransaction,
  CanPayDecision,
  Delegation,
  PaymentIntentProposal,
  PaymentResult,
  ProofBundle,
  UserConfirmation,
} from "./domain/types.ts";

export interface AgentEnrollment {
  agent_id: string;
  key_id: string;
  pubkey: string;
}

interface IntentRecord {
  intent_id: string;
  delegation_id: string;
  proposal: PaymentIntentProposal;
  bound: BoundTransaction;
  agent_key_id: string;
  decision: CanPayDecision;
  created_at: number;
}

export interface CreateIntentResult {
  intent_id: string;
  decision: CanPayDecision;
  bound: BoundTransaction;
}

export interface AuthorizeResult {
  intent_id: string;
  decision: CanPayDecision;
  payment: PaymentResult | null;
  proof_bundle: ProofBundle;
}

export class ControlPlane {
  readonly keys: KeyService;
  readonly delegations: DelegationService;
  readonly binding: BindingService;
  readonly risk: RiskEngine;
  readonly audit: AuditLedger;
  readonly spend: SpendLedger;
  readonly broker: BrokerOrchestrator;
  readonly recon: ReconciliationWorker;
  #clock: Clock;
  #intents = new Map<string, IntentRecord>();
  #intentTimes = new Map<string, number[]>(); // delegation_id -> createPaymentIntent timestamps

  constructor(opts: { clock?: Clock; provider?: ProviderAdapter } = {}) {
    this.#clock = opts.clock ?? systemClock;
    this.keys = new KeyService();
    this.audit = new AuditLedger(this.#clock);
    this.delegations = new DelegationService(this.audit, this.#clock);
    this.binding = new BindingService(this.keys);
    this.risk = new RiskEngine();
    this.spend = new SpendLedger();
    const provider = opts.provider ?? new MockProvider();
    this.broker = new BrokerOrchestrator(provider, this.audit, this.spend, this.#clock);
    this.recon = new ReconciliationWorker(this.broker, provider, this.audit, this.spend, this.#clock);
  }

  // --- Agent + delegation lifecycle -----------------------------------------
  enrollAgent(agentId = "syncore_" + randomUUID().slice(0, 8)): AgentEnrollment {
    const handle = this.keys.generateAgentKey();
    return { agent_id: agentId, key_id: handle.key_id, pubkey: handle.pubkey };
  }

  createDelegation(
    input: Omit<CreateDelegationInput, "agent"> & { agent: AgentEnrollment },
    userKey: UserPasskey,
  ): Delegation {
    return this.delegations.createDelegation(
      {
        ...input,
        agent: { id: input.agent.agent_id, key_id: input.agent.key_id, pubkey: input.agent.pubkey },
      },
      userKey,
    );
  }

  /** Agent-side helper: produce a DPoP-style proof bound to the agent key. */
  makeAgentProof(enrollment: AgentEnrollment, context: unknown): AgentProof {
    const over = canonicalJson(context);
    return {
      agent_id: enrollment.agent_id,
      key_id: enrollment.key_id,
      over,
      sig: this.keys.sign(enrollment.key_id, over),
    };
  }

  // --- The one payment door -------------------------------------------------
  createPaymentIntent(args: {
    delegation_id: string;
    proposal: PaymentIntentProposal;
    proof: AgentProof;
    confirmation?: UserConfirmation;
  }): CreateIntentResult {
    const now = this.#clock();
    const delegation = this.delegations.get(args.delegation_id);
    if (!delegation) throw new Error("unknown delegation");

    const intentId = "pi_" + randomUUID().replace(/-/g, "").slice(0, 20);

    // Bind first (cart hash + single-use nonce + agent signature) — W3.
    const bound = this.binding.bind(args.proposal, delegation, intentId, now);

    // Record this intent's timestamp once (velocity signal source).
    const times = this.#intentTimes.get(args.delegation_id) ?? [];
    times.push(now.getTime());
    this.#intentTimes.set(args.delegation_id, times);

    const rec: IntentRecord = {
      intent_id: intentId,
      delegation_id: args.delegation_id,
      proposal: args.proposal,
      bound,
      agent_key_id: args.proof.key_id,
      decision: undefined as unknown as CanPayDecision, // set by #gate below
      created_at: now.getTime(),
    };

    const agentProofValid =
      args.proof.key_id === delegation.agent.key_id &&
      verifySignature(delegation.agent.pubkey, args.proof.over, args.proof.sig);

    const decision = this.#gate(rec, delegation, agentProofValid, args.confirmation ?? null);
    rec.decision = decision;
    this.#intents.set(intentId, rec);
    return { intent_id: intentId, decision, bound };
  }

  /** Assemble the CAN_PAY input for one intent and evaluate it. Pure w.r.t.
   *  external state; appends the decision to the audit chain (B4). */
  #gate(
    rec: IntentRecord,
    delegation: Delegation,
    agentProofValid: boolean,
    confirmation: UserConfirmation | null,
  ): CanPayDecision {
    const now = this.#clock();
    const times = this.#intentTimes.get(rec.delegation_id) ?? [];
    const recent60s = times.filter((t) => now.getTime() - t <= 60_000).length;

    const risk = this.risk.score(rec.proposal, delegation, {
      recent_intents_60s: recent60s,
      avg_recent_spend_paise: this.spend.recentAverage(rec.delegation_id, now),
      delegation_age_seconds: (now.getTime() - Date.parse(delegation.valid_from)) / 1000,
    });

    const confirmationValid = confirmation
      ? this.#verifyConfirmation(rec.intent_id, rec.proposal, confirmation)
      : false;

    const input: CanPayInput = {
      now,
      delegation,
      effectiveStatus: this.delegations.effectiveStatus(delegation),
      userSignatureValid: this.delegations.verifyUserSignature(delegation),
      agentProofValid,
      agentKeyId: rec.agent_key_id,
      proposal: rec.proposal,
      bound: rec.bound,
      bindingValid: this.binding.verifyBinding(rec.bound),
      nonceFresh: this.binding.isNonceFresh(rec.bound.nonce, now),
      ledger: this.spend.view(rec.delegation_id, now),
      risk,
      confirmation,
      confirmationValid,
    };

    const decision = canPay(input);
    // B4: append the decision to the audit chain BEFORE any side effect.
    this.audit.append("policy-gate", "CANPAY_DECISION", rec.intent_id, {
      decision: decision.decision,
      rule_fired: decision.rule_fired,
      checks: decision.checks,
      risk: decision.risk,
    });
    return decision;
  }

  /** Authorize: consume the single-use nonce and execute — only on ALLOW. */
  authorize(intentId: string): AuthorizeResult {
    const rec = this.#requireIntent(intentId);
    const now = this.#clock();

    if (rec.decision.decision !== "ALLOW") {
      return { intent_id: intentId, decision: rec.decision, payment: null, proof_bundle: this.proofBundle(intentId) };
    }

    // Single-use nonce consumption at authorize time (replay/expiry => abort).
    if (!this.binding.consumeNonce(rec.bound.nonce, now)) {
      this.audit.append("policy-gate", "AUTHORIZE_ABORTED", intentId, { reason: "nonce not consumable" });
      return { intent_id: intentId, decision: rec.decision, payment: null, proof_bundle: this.proofBundle(intentId) };
    }

    this.audit.append("policy-gate", "AUTHORIZED", intentId, { nonce: rec.bound.nonce });
    const payment = this.broker.execute(rec.bound, rec.decision);
    return { intent_id: intentId, decision: rec.decision, payment, proof_bundle: this.proofBundle(intentId) };
  }

  /** Resolve a CHALLENGE with a fresh user confirmation, then re-gate the SAME
   *  intent (same bound + still-fresh nonce) and authorize — never a new intent. */
  confirmAndAuthorize(intentId: string, userKey: UserPasskey): AuthorizeResult {
    const rec = this.#requireIntent(intentId);
    const delegation = this.delegations.get(rec.delegation_id);
    if (!delegation) throw new Error("unknown delegation");

    const confirmation = this.#buildConfirmation(rec.intent_id, rec.proposal, userKey);
    // Re-authenticate the agent for the confirmation step.
    const proof = this.makeAgentProof(
      { agent_id: rec.bound.agent_id, key_id: rec.agent_key_id, pubkey: rec.bound.agent_pubkey },
      { intent: intentId, step: "confirm" },
    );
    const agentProofValid =
      proof.key_id === delegation.agent.key_id &&
      verifySignature(delegation.agent.pubkey, proof.over, proof.sig);

    rec.decision = this.#gate(rec, delegation, agentProofValid, confirmation);
    return this.authorize(intentId);
  }

  proofBundle(intentId: string): ProofBundle {
    return this.audit.bundle(intentId);
  }

  // --- confirmation helpers -------------------------------------------------
  #confirmationBytes(intentId: string, proposal: PaymentIntentProposal): string {
    return canonicalJson({ intent_id: intentId, amount_paise: proposal.amount_paise, merchant: proposal.merchant });
  }

  #buildConfirmation(intentId: string, proposal: PaymentIntentProposal, userKey: UserPasskey): UserConfirmation {
    const over = this.#confirmationBytes(intentId, proposal);
    return { over, sig: userKey.sign(over), key: userKey.pubkey, issued_at: this.#clock().toISOString() };
  }

  #verifyConfirmation(intentId: string, proposal: PaymentIntentProposal, c: UserConfirmation): boolean {
    if (c.over !== this.#confirmationBytes(intentId, proposal)) return false;
    return UserPasskey.verify(c.key, c.over, c.sig);
  }

  #requireIntent(intentId: string): IntentRecord {
    const rec = this.#intents.get(intentId);
    if (!rec) throw new Error("unknown intent");
    return rec;
  }
}
