/**
 * Payment state machine (Blueprint 8.1, Figures 8.1/8.2).
 *
 * One happy path, three outcomes, worker-owned promotion. The ambient rule:
 * NO financial action is ever triggered from an ambiguous state. UNKNOWN is a
 * first-class state that only a worker can promote to SETTLED or DROPPED; there
 * is no EXECUTE edge out of UNKNOWN, so a timed-out payment can never be blindly
 * re-executed. FAILED is terminal — the failed intent can never be retried,
 * which makes retry storms structurally impossible.
 */

import type { PaymentEvent, PaymentState } from "../domain/types.ts";

export const TRANSITIONS: Record<PaymentState, Partial<Record<PaymentEvent, PaymentState>>> = {
  PENDING: { EXECUTE: "EXECUTING" },
  EXECUTING: {
    PROVIDER_SUCCESS: "SUCCESS",
    PROVIDER_FAILED: "FAILED",
    PROVIDER_TIMEOUT: "UNKNOWN",
  },
  SUCCESS: { FINALIZE: "SETTLED" },
  UNKNOWN: { RECON_SETTLED: "SETTLED", RECON_DROPPED: "DROPPED" },
  FAILED: {},
  SETTLED: {},
  DROPPED: {},
};

export const TERMINAL_STATES: readonly PaymentState[] = ["SETTLED", "DROPPED", "FAILED"];

export function isTerminal(state: PaymentState): boolean {
  return TERMINAL_STATES.includes(state);
}

export function canTransition(state: PaymentState, event: PaymentEvent): boolean {
  return TRANSITIONS[state][event] !== undefined;
}

/** Pure transition. Throws on an undefined edge (the machine is total by
 *  rejecting everything not explicitly allowed — fail closed). */
export function transition(state: PaymentState, event: PaymentEvent): PaymentState {
  const next = TRANSITIONS[state][event];
  if (next === undefined) {
    throw new Error(`illegal transition: ${state} --${event}--> ?`);
  }
  return next;
}
