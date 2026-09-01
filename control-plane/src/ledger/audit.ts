/**
 * Audit Ledger (Blueprint 5.2, 7.3, W7).
 *
 * Append-only, hash-chained evidence store. Every Zone 1 decision is appended
 * BEFORE any side effect (rule B4). Each entry's hash covers the previous
 * hash plus the canonical payload, so any tampering (edit, reorder, delete)
 * breaks the chain and is caught by the verifier.
 *
 * The proof bundle (W7) is simply the chain slice for one intent plus a
 * verification verdict — the artifact that makes an agent-spent rupee
 * disputable after the fact.
 */

import { type Clock, systemClock } from "../domain/clock.ts";
import { canonicalJson, sha256Hex } from "../crypto/canonical.ts";
import type { AuditEvent, ProofBundle } from "../domain/types.ts";

const GENESIS = "GENESIS";

function computeEntryHash(
  prevHash: string,
  core: Omit<AuditEvent, "prev_hash" | "entry_hash">,
): string {
  return sha256Hex(prevHash + "\n" + canonicalJson(core));
}

export class AuditLedger {
  #events: AuditEvent[] = [];
  #clock: Clock;

  constructor(clock: Clock = systemClock) {
    this.#clock = clock;
  }

  append(actor: string, type: string, intentId: string | null, payload: unknown): AuditEvent {
    const prevHash = this.#events.length
      ? this.#events[this.#events.length - 1]!.entry_hash
      : GENESIS;
    const core = {
      seq: this.#events.length,
      at: this.#clock().toISOString(),
      actor,
      type,
      intent_id: intentId,
      payload,
    };
    const entry: AuditEvent = {
      ...core,
      prev_hash: prevHash,
      entry_hash: computeEntryHash(prevHash, core),
    };
    this.#events.push(entry);
    return entry;
  }

  /** Walk the chain and confirm every link. Returns the first broken seq if any. */
  verifyChain(): { valid: boolean; brokenAt: number | null } {
    let prev = GENESIS;
    for (const e of this.#events) {
      const { prev_hash, entry_hash, ...core } = e;
      if (prev_hash !== prev) return { valid: false, brokenAt: e.seq };
      if (computeEntryHash(prev_hash, core) !== entry_hash) return { valid: false, brokenAt: e.seq };
      prev = entry_hash;
    }
    return { valid: true, brokenAt: null };
  }

  bundle(intentId: string): ProofBundle {
    const chain = this.verifyChain();
    return {
      intent_id: intentId,
      events: this.#events.filter((e) => e.intent_id === intentId),
      chain_valid: chain.valid,
    };
  }

  all(): readonly AuditEvent[] {
    return this.#events;
  }

  /** Test-only escape hatch to simulate tampering and prove the verifier bites. */
  _unsafeMutateForTest(seq: number, mutate: (e: AuditEvent) => void): void {
    const e = this.#events[seq];
    if (e) mutate(e);
  }
}
