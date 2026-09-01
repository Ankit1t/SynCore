/**
 * Shared test harness. Not a test file itself (no test() calls).
 */

import { ControlPlane } from "../src/controlPlane.ts";
import { UserPasskey } from "../src/crypto/keys.ts";
import { FakeClock } from "../src/domain/clock.ts";
import { MockProvider } from "../src/broker/mockProvider.ts";
import { canPay, type CanPayInput } from "../src/policy/canPay.ts";
import type { Delegation, PaymentIntentProposal } from "../src/domain/types.ts";

export interface Harness {
  clock: FakeClock;
  provider: MockProvider;
  cp: ControlPlane;
  agent: ReturnType<ControlPlane["enrollAgent"]>;
  user: UserPasskey;
  delegation: Delegation;
}

export function newHarness(
  opts: {
    start?: string;
    require_confirmation_above_paise?: number;
    per_tx?: number;
    daily?: number;
  } = {},
): Harness {
  const clock = new FakeClock(opts.start ?? "2026-09-01T10:00:00.000Z");
  const provider = new MockProvider();
  const cp = new ControlPlane({ clock: clock.now, provider });
  const agent = cp.enrollAgent("agent_test");
  const user = new UserPasskey();
  const delegation = cp.createDelegation(
    {
      principal: "user_123",
      agent,
      purpose: "grocery_purchase",
      merchant_scope: { mode: "allowlist", merchants: ["zepto", "blinkit", "bigbasket"] },
      category_scope: ["grocery"],
      limits_paise: {
        per_tx: opts.per_tx ?? 50000,
        daily: opts.daily ?? 150000,
        weekly: 400000,
        monthly: 1500000,
      },
      price_drift_bps: 0,
      substitution: "ASK",
      require_confirmation_above_paise: opts.require_confirmation_above_paise ?? 50000,
      expires_at: "2026-09-30T00:00:00.000Z",
    },
    user,
  );
  return { clock, provider, cp, agent, user, delegation };
}

export function groceryProposal(overrides: Partial<PaymentIntentProposal> = {}): PaymentIntentProposal {
  return {
    purpose: "grocery_purchase",
    merchant: "zepto",
    category: "grocery",
    cart: [
      { sku: "potato-1kg", qty: 1, unit_paise: 3200 },
      { sku: "maggi-70g", qty: 5, unit_paise: 1400 },
    ],
    amount_paise: 10200,
    currency: "INR",
    ...overrides,
  };
}

let counter = 0;
export function freshProof(h: Harness) {
  return h.cp.makeAgentProof(h.agent, { n: counter++ });
}

/**
 * Assemble a CAN_PAY input directly so a test can bind ONE proposal and gate a
 * DIFFERENT one (to exercise price-drift / cart-swap), or override any field.
 */
export function evaluateGate(
  h: Harness,
  args: {
    delegation?: Delegation;
    boundProposal: PaymentIntentProposal;
    gateProposal?: PaymentIntentProposal;
    overrides?: Partial<CanPayInput>;
  },
) {
  const delegation = args.delegation ?? h.delegation;
  const gateProposal = args.gateProposal ?? args.boundProposal;
  const now = h.clock.now();
  const bound = h.cp.binding.bind(args.boundProposal, delegation, "pi_test_" + counter++, now);
  const input: CanPayInput = {
    now,
    delegation,
    effectiveStatus: h.cp.delegations.effectiveStatus(delegation),
    userSignatureValid: h.cp.delegations.verifyUserSignature(delegation),
    agentProofValid: true,
    agentKeyId: delegation.agent.key_id,
    proposal: gateProposal,
    bound,
    bindingValid: h.cp.binding.verifyBinding(bound),
    nonceFresh: h.cp.binding.isNonceFresh(bound.nonce, now),
    ledger: h.cp.spend.view(delegation.delegation_id, now),
    risk: h.cp.risk.score(gateProposal, delegation, {
      recent_intents_60s: 0,
      avg_recent_spend_paise: 0,
      delegation_age_seconds: 3600,
    }),
    confirmation: null,
    confirmationValid: false,
    ...args.overrides,
  };
  return canPay(input);
}
