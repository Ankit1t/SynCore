/**
 * Idempotency + reconciliation drills (Blueprint 8.1, W6, Gate G1b preview).
 * "Duplicate-submit and timeout-chaos drills produce exactly one payment or
 * zero payments, never two."
 */

import test from "node:test";
import assert from "node:assert/strict";
import { newHarness, groceryProposal, freshProof } from "./helpers.ts";

function pay(h: ReturnType<typeof newHarness>) {
  const intent = h.cp.createPaymentIntent({
    delegation_id: h.delegation.delegation_id,
    proposal: groceryProposal(),
    proof: freshProof(h),
  });
  return h.cp.authorize(intent.intent_id);
}

test("timeout -> UNKNOWN -> reconcile promotes to SETTLED with exactly one charge", () => {
  const h = newHarness();
  h.provider.scriptOutcomes("TIMEOUT");
  const res = pay(h);
  assert.equal(res.payment?.state, "UNKNOWN");
  const rec = h.cp.recon.reconcile(res.intent_id);
  assert.equal(rec.outcome, "SETTLED"); // provider ground-truth says the money moved
  assert.equal(h.provider.totalCharges(), 1);
});

test("failed payment is terminal and never charges", () => {
  const h = newHarness();
  h.provider.scriptOutcomes("FAILED");
  const res = pay(h);
  assert.equal(res.payment?.state, "FAILED");
  assert.equal(h.provider.totalCharges(), 0);
});

test("reconcile is a no-op on a non-UNKNOWN transaction", () => {
  const h = newHarness();
  const res = pay(h); // SUCCESS -> SETTLED
  const rec = h.cp.recon.reconcile(res.intent_id);
  assert.equal(rec.outcome, "NOOP");
  assert.equal(h.provider.totalCharges(), 1);
});

test("provider-level idempotency: same key never double-charges", () => {
  const h = newHarness();
  const first = pay(h);
  assert.equal(first.payment?.state, "SETTLED");
  // A second authorize of the same intent cannot re-execute (nonce consumed),
  // and even a direct provider replay with the same key returns the cached ref.
  const second = h.cp.authorize(first.intent_id);
  assert.equal(second.payment, null);
  assert.equal(h.provider.totalCharges(), 1);
});

test("audit chain stays valid across timeout + reconciliation", () => {
  const h = newHarness();
  h.provider.scriptOutcomes("TIMEOUT");
  const res = pay(h);
  h.cp.recon.reconcile(res.intent_id);
  assert.equal(h.cp.audit.verifyChain().valid, true);
  const bundle = h.cp.proofBundle(res.intent_id);
  const types = bundle.events.map((e) => e.type);
  assert.ok(types.includes("PAYMENT_UNKNOWN"));
  assert.ok(types.includes("PAYMENT_SETTLED"));
});
