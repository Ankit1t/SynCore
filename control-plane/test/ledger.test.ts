/**
 * Gate G0 — audit ledger hash chain (Blueprint 7.3, W7).
 * Proves the chain verifies clean, that tampering (edit / reorder) is detected,
 * and that a proof bundle isolates one intent's evidence.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { AuditLedger } from "../src/ledger/audit.ts";
import { FakeClock } from "../src/domain/clock.ts";

function ledger() {
  const clock = new FakeClock();
  return new AuditLedger(clock.now);
}

test("a clean chain verifies", () => {
  const l = ledger();
  l.append("a", "E1", "pi_1", { x: 1 });
  l.append("b", "E2", "pi_1", { x: 2 });
  l.append("c", "E3", "pi_2", { x: 3 });
  assert.deepEqual(l.verifyChain(), { valid: true, brokenAt: null });
});

test("tampering with a payload breaks the chain at that seq", () => {
  const l = ledger();
  l.append("a", "E1", "pi_1", { amount: 100 });
  l.append("b", "E2", "pi_1", { amount: 200 });
  l.append("c", "E3", "pi_1", { amount: 300 });
  // An attacker rewrites the amount of event seq 1 in place.
  l._unsafeMutateForTest(1, (e) => {
    (e.payload as { amount: number }).amount = 999999;
  });
  const res = l.verifyChain();
  assert.equal(res.valid, false);
  assert.equal(res.brokenAt, 1);
});

test("proof bundle isolates one intent and reports chain validity", () => {
  const l = ledger();
  l.append("a", "CANPAY_DECISION", "pi_1", {});
  l.append("b", "CANPAY_DECISION", "pi_2", {});
  l.append("c", "PAYMENT_SETTLED", "pi_1", {});
  const bundle = l.bundle("pi_1");
  assert.equal(bundle.events.length, 2);
  assert.ok(bundle.events.every((e) => e.intent_id === "pi_1"));
  assert.equal(bundle.chain_valid, true);
});
