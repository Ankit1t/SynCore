/**
 * CAN_PAY() — the deterministic policy gate (Blueprint 6.1, Table 6.1, W2).
 *
 * A pure function from (delegation, proposal, ledger, risk, binding, proofs) to
 * {ALLOW, CHALLENGE, DENY} plus a machine-readable reason. Twelve checks in a
 * FIXED order; evaluation stops at the first non-PASS (an attacker learns only
 * the earliest failing rule). No network calls. No model calls. Fails closed:
 * any unclassifiable condition is DENY. Every evaluation yields a decision
 * record the Audit Ledger chains.
 */

import { hashCanonical } from "../crypto/canonical.ts";
import type {
  BoundTransaction,
  CanPayDecision,
  CheckResult,
  Decision,
  Delegation,
  DelegationStatus,
  LedgerView,
  PaymentIntentProposal,
  RiskVerdict,
  UserConfirmation,
} from "../domain/types.ts";

export interface CanPayInput {
  now: Date;
  delegation: Delegation;
  effectiveStatus: DelegationStatus;
  userSignatureValid: boolean;
  agentProofValid: boolean;
  agentKeyId: string; // key id presented by the agent proof
  proposal: PaymentIntentProposal;
  bound: BoundTransaction;
  bindingValid: boolean;
  nonceFresh: boolean;
  ledger: LedgerView;
  risk: RiskVerdict;
  confirmation: UserConfirmation | null;
  confirmationValid: boolean;
}

type CheckOutcome = { outcome: Decision | "PASS"; detail: string };

const PASS: CheckOutcome = { outcome: "PASS", detail: "ok" };
const deny = (detail: string): CheckOutcome => ({ outcome: "DENY", detail });
const challenge = (detail: string): CheckOutcome => ({ outcome: "CHALLENGE", detail });

/** The twelve checks, in the frozen order. Each is a pure predicate. */
const CHECKS: Array<{ name: string; run: (i: CanPayInput) => CheckOutcome }> = [
  {
    name: "AUTH_IDENTITY",
    run: (i) => {
      if (!i.agentProofValid) return deny("agent proof invalid");
      if (!i.userSignatureValid) return deny("delegation user signature invalid");
      if (!i.bindingValid) return deny("binding signature invalid");
      if (i.agentKeyId !== i.delegation.agent.key_id) return deny("agent key mismatch");
      if (i.bound.agent_pubkey !== i.delegation.agent.pubkey) return deny("bound key mismatch");
      return PASS;
    },
  },
  {
    name: "DELEGATION_STATE",
    run: (i) =>
      i.delegation.status === "ACTIVE" ? PASS : deny(`delegation ${i.delegation.status}`),
  },
  {
    name: "TIME_WINDOW",
    run: (i) => {
      const t = i.now.getTime();
      if (t < Date.parse(i.delegation.valid_from)) return deny("before valid_from");
      if (t >= Date.parse(i.delegation.expires_at)) return deny("delegation expired");
      if (i.effectiveStatus === "EXPIRED") return deny("delegation expired");
      return PASS;
    },
  },
  {
    name: "MERCHANT_SCOPE",
    run: (i) => {
      const s = i.delegation.merchant_scope;
      if (s.mode === "allowlist" && !s.merchants.includes(i.bound.merchant)) {
        return deny(`merchant ${i.bound.merchant} not in allowlist`);
      }
      return PASS;
    },
  },
  {
    name: "CATEGORY_SCOPE",
    run: (i) =>
      i.delegation.category_scope.includes(i.proposal.category)
        ? PASS
        : deny(`category ${i.proposal.category} out of scope`),
  },
  {
    name: "PER_TX_LIMIT",
    run: (i) =>
      i.bound.amount_paise <= i.delegation.limits_paise.per_tx
        ? PASS
        : deny(`amount ${i.bound.amount_paise} over per_tx ${i.delegation.limits_paise.per_tx}`),
  },
  {
    name: "VELOCITY",
    run: (i) => {
      const L = i.delegation.limits_paise;
      const a = i.bound.amount_paise;
      if (i.ledger.spent_daily_paise + a > L.daily) return deny("daily limit exceeded");
      if (i.ledger.spent_weekly_paise + a > L.weekly) return deny("weekly limit exceeded");
      if (i.ledger.spent_monthly_paise + a > L.monthly) return deny("monthly limit exceeded");
      return PASS;
    },
  },
  {
    name: "PRICE_DRIFT",
    run: (i) => {
      const bound = i.bound.amount_paise;
      const current = i.proposal.amount_paise;
      const allowed = Math.floor((bound * i.delegation.price_drift_bps) / 10000);
      return Math.abs(current - bound) <= allowed
        ? PASS
        : deny(`price drift ${current - bound} paise beyond ${allowed}`);
    },
  },
  {
    name: "CART_BINDING",
    run: (i) => {
      if (i.bound.merchant !== i.proposal.merchant) return deny("merchant mutated after binding");
      return hashCanonical(i.proposal.cart) === i.bound.cart_hash
        ? PASS
        : deny("cart mutated after binding");
    },
  },
  {
    name: "CONFIRMATION",
    run: (i) => {
      const threshold = i.delegation.require_confirmation_above_paise;
      if (i.bound.amount_paise <= threshold) return PASS;
      if (i.confirmation && i.confirmationValid) return PASS;
      return challenge(`amount above confirmation threshold ${threshold}; user yes required`);
    },
  },
  {
    name: "RISK_GATE",
    run: (i) => {
      // HIGH can never be overridden by a confirmation; MEDIUM pauses for a
      // user yes and proceeds once a fresh valid confirmation is present.
      if (i.risk.level === "HIGH") return deny(`risk HIGH: ${i.risk.reason}`);
      if (i.risk.level === "MEDIUM") {
        return i.confirmation && i.confirmationValid
          ? PASS
          : challenge(`risk MEDIUM: ${i.risk.reason}`);
      }
      return PASS;
    },
  },
  {
    name: "NONCE_FRESH",
    run: (i) => (i.nonceFresh ? PASS : deny("nonce missing, expired, or replayed")),
  },
];

export function canPay(input: CanPayInput): CanPayDecision {
  const checks: CheckResult[] = [];
  let decision: Decision = "ALLOW";
  let ruleFired: string | null = null;

  for (let idx = 0; idx < CHECKS.length; idx++) {
    const c = CHECKS[idx]!;
    let res: CheckOutcome;
    try {
      res = c.run(input);
    } catch (err) {
      // Any exception in a check is treated as a denial — fail closed.
      res = deny(`check error: ${(err as Error).message}`);
    }
    checks.push({
      index: idx + 1,
      name: c.name,
      passed: res.outcome === "PASS",
      outcome: res.outcome,
      detail: res.detail,
    });
    if (res.outcome !== "PASS") {
      decision = res.outcome;
      ruleFired = c.name;
      break; // first non-PASS wins; attacker learns only the earliest rule
    }
  }

  return {
    decision,
    rule_fired: ruleFired,
    checks,
    risk: input.risk,
    decided_at: input.now.toISOString(),
  };
}
