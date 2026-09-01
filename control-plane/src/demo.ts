/**
 * End-to-end demo of the SYNCCORE Agent Financial Control Plane.
 *
 *   node src/demo.ts
 *
 * Shows the two worked examples from Blueprint 6.1:
 *   1. INR 427 at a named grocery merchant, clean -> ALLOW -> executed -> proof bundle.
 *   2. INR 4270 at an unknown electronics merchant -> DENY at MERCHANT_SCOPE (check 4).
 * Plus a duplicate-submit drill proving exactly one charge.
 */

import { ControlPlane } from "./controlPlane.ts";
import { UserPasskey } from "./crypto/keys.ts";
import { FakeClock } from "./domain/clock.ts";
import { MockProvider } from "./broker/mockProvider.ts";
import type { PaymentIntentProposal } from "./domain/types.ts";

const rupees = (paise: number) => "INR " + (paise / 100).toFixed(2);

function line(char = "-") {
  console.log(char.repeat(72));
}

const clock = new FakeClock("2026-09-01T10:00:00.000Z");
const provider = new MockProvider();
const cp = new ControlPlane({ clock: clock.now, provider });

// 1. Enroll agent + user signs a grocery delegation (the frozen default artifact).
const agent = cp.enrollAgent("syncore_grocery_01");
const user = new UserPasskey();
const delegation = cp.createDelegation(
  {
    principal: "user_123",
    agent,
    purpose: "grocery_purchase",
    merchant_scope: { mode: "allowlist", merchants: ["zepto", "blinkit", "bigbasket"] },
    category_scope: ["grocery"],
    limits_paise: { per_tx: 50000, daily: 150000, weekly: 400000, monthly: 1500000 },
    price_drift_bps: 0,
    substitution: "ASK",
    require_confirmation_above_paise: 50000,
    expires_at: "2026-09-30T00:00:00.000Z",
  },
  user,
);

line("=");
console.log("SYNCCORE Agent Financial Control Plane — demo");
console.log(`Delegation ${delegation.delegation_id} v${delegation.version} for agent ${agent.agent_id}`);
console.log(`Limits: per_tx ${rupees(50000)}, daily ${rupees(150000)}; merchants zepto/blinkit/bigbasket`);
console.log(`User signature valid: ${cp.delegations.verifyUserSignature(delegation)}`);
line("=");

// 2. ALLOW case: INR 427 at zepto (grocery).
const okProposal: PaymentIntentProposal = {
  purpose: "grocery_purchase",
  merchant: "zepto",
  category: "grocery",
  cart: [
    { sku: "potato-1kg", qty: 1, unit_paise: 3200 },
    { sku: "onion-1kg", qty: 1, unit_paise: 3500 },
    { sku: "maggi-70g", qty: 5, unit_paise: 1400 },
  ],
  amount_paise: 42700,
  currency: "INR",
};
const proof1 = cp.makeAgentProof(agent, { m: "POST", p: "/v1/payment-intents", merchant: "zepto" });
const intent1 = cp.createPaymentIntent({ delegation_id: delegation.delegation_id, proposal: okProposal, proof: proof1 });
console.log(`\nCASE 1  ${rupees(okProposal.amount_paise)} @ ${okProposal.merchant}`);
console.log(`  CAN_PAY -> ${intent1.decision.decision} (rule_fired: ${intent1.decision.rule_fired ?? "none"})`);
console.log(`  checks: ${intent1.decision.checks.map((c) => `${c.index}:${c.name}=${c.outcome}`).join("  ")}`);
const auth1 = cp.authorize(intent1.intent_id);
console.log(`  authorize -> payment ${auth1.payment?.state} via ${auth1.payment?.provider} ref ${auth1.payment?.provider_ref}`);
console.log(`  proof bundle: ${auth1.proof_bundle.events.length} chained events, chain_valid=${auth1.proof_bundle.chain_valid}`);

// 3. DENY case: INR 4270 at an unknown electronics merchant.
const badProposal: PaymentIntentProposal = {
  purpose: "grocery_purchase",
  merchant: "shady-electronics",
  category: "electronics",
  cart: [{ sku: "phone", qty: 1, unit_paise: 427000 }],
  amount_paise: 427000,
  currency: "INR",
};
const proof2 = cp.makeAgentProof(agent, { m: "POST", p: "/v1/payment-intents", merchant: "shady-electronics" });
const intent2 = cp.createPaymentIntent({ delegation_id: delegation.delegation_id, proposal: badProposal, proof: proof2 });
console.log(`\nCASE 2  ${rupees(badProposal.amount_paise)} @ ${badProposal.merchant}`);
console.log(`  CAN_PAY -> ${intent2.decision.decision} (rule_fired: ${intent2.decision.rule_fired})`);
const auth2 = cp.authorize(intent2.intent_id);
console.log(`  authorize -> payment executed: ${auth2.payment !== null} (must be false)`);

// 4. Duplicate-submit drill: authorize the SAME allowed intent twice.
const dupIntent = cp.createPaymentIntent({
  delegation_id: delegation.delegation_id,
  proposal: okProposal,
  proof: cp.makeAgentProof(agent, { m: "POST", p: "/v1/payment-intents", merchant: "zepto", n: 2 }),
});
const first = cp.authorize(dupIntent.intent_id);
const second = cp.authorize(dupIntent.intent_id); // nonce already consumed
console.log(`\nCASE 3  duplicate authorize`);
console.log(`  first  -> ${first.payment?.state}`);
console.log(`  second -> executed again: ${second.payment !== null && second.payment.state !== first.payment?.state}`);
console.log(`  provider total charges (case1 + case3 = 2 expected): ${provider.totalCharges()}`);

line("=");
console.log(`Audit chain valid across all events: ${cp.audit.verifyChain().valid}`);
console.log(`Total audit events: ${cp.audit.all().length}`);
line("=");
