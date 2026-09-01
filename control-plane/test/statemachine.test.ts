/**
 * Gate G0 — state machine invariants (Blueprint 10, Table 10.1).
 *
 * Proves: the machine is total (every input maps to a defined transition or a
 * rejection), there are no skip transitions, UNKNOWN never executes, terminal
 * states are truly terminal, and every real transition emits an audit event.
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
  TRANSITIONS,
  TERMINAL_STATES,
  canTransition,
  isTerminal,
  transition,
} from "../src/statemachine/payment.ts";
import type { PaymentEvent, PaymentState } from "../src/domain/types.ts";
import { newHarness, groceryProposal, freshProof } from "./helpers.ts";

const ALL_STATES: PaymentState[] = [
  "PENDING", "EXECUTING", "SUCCESS", "FAILED", "UNKNOWN", "SETTLED", "DROPPED",
];
const ALL_EVENTS: PaymentEvent[] = [
  "EXECUTE", "PROVIDER_SUCCESS", "PROVIDER_FAILED", "PROVIDER_TIMEOUT",
  "RECON_SETTLED", "RECON_DROPPED", "FINALIZE",
];

test("machine is total: every (state,event) either maps or throws — never undefined", () => {
  for (const s of ALL_STATES) {
    for (const e of ALL_EVENTS) {
      if (canTransition(s, e)) {
        const next = transition(s, e);
        assert.ok(ALL_STATES.includes(next), `${s}+${e} -> valid state`);
      } else {
        assert.throws(() => transition(s, e), `${s}+${e} must be rejected (fail closed)`);
      }
    }
  }
});

test("no skip transitions: EXECUTING is reachable ONLY from PENDING via EXECUTE", () => {
  for (const s of ALL_STATES) {
    for (const e of ALL_EVENTS) {
      if (canTransition(s, e) && transition(s, e) === "EXECUTING") {
        assert.equal(s, "PENDING");
        assert.equal(e, "EXECUTE");
      }
    }
  }
});

test("UNKNOWN never executes: no EXECUTE edge out of UNKNOWN", () => {
  assert.equal(canTransition("UNKNOWN", "EXECUTE"), false);
  // The only ways out of UNKNOWN are worker-owned promotions.
  const outs = Object.keys(TRANSITIONS.UNKNOWN);
  assert.deepEqual(outs.sort(), ["RECON_DROPPED", "RECON_SETTLED"]);
});

test("terminal states have no outgoing transitions", () => {
  for (const s of TERMINAL_STATES) {
    assert.equal(Object.keys(TRANSITIONS[s]).length, 0, `${s} is terminal`);
    assert.ok(isTerminal(s));
  }
  assert.equal(isTerminal("EXECUTING"), false);
});

test("FAILED is terminal — a failed intent can never be retried", () => {
  for (const e of ALL_EVENTS) {
    assert.equal(canTransition("FAILED", e), false);
  }
});

test("every state transition of a real payment emits an audit event", () => {
  const h = newHarness();
  const intent = h.cp.createPaymentIntent({
    delegation_id: h.delegation.delegation_id,
    proposal: groceryProposal(),
    proof: freshProof(h),
  });
  assert.equal(intent.decision.decision, "ALLOW");
  const res = h.cp.authorize(intent.intent_id);
  assert.equal(res.payment?.state, "SETTLED");

  const types = res.proof_bundle.events.map((e) => e.type);
  // decision recorded before side effects, then the full transition chain.
  for (const expected of [
    "CANPAY_DECISION", "AUTHORIZED", "PAYMENT_PENDING",
    "PAYMENT_EXECUTING", "PAYMENT_SUCCESS", "PAYMENT_SETTLED",
  ]) {
    assert.ok(types.includes(expected), `audit chain missing ${expected}: ${types.join(",")}`);
  }
});
