/**
 * Binding Service (Blueprint 5.2, W3).
 *
 * Binds every authorization to exactly one transaction: canonical cart hash,
 * amount, currency, merchant, agent key, and a single-use nonce, signed by the
 * agent key. The executed payment must match this bound tuple; any cart
 * mutation or amount drift breaks the hash and is a DENY, never a warning.
 *
 * The nonce registry is single-use with a 60s replay window (Redis in prod).
 */

import { randomUUID } from "node:crypto";
import { canonicalJson, hashCanonical } from "./canonical.ts";
import { verifySignature, type KeyService } from "./keys.ts";
import type { BoundTransaction, Delegation, PaymentIntentProposal } from "../domain/types.ts";

const NONCE_WINDOW_MS = 60_000;

interface NonceRecord {
  nonce: string;
  delegation_id: string;
  intent_id: string;
  expires_at: number;
  consumed: boolean;
}

/** The canonical bytes the agent signs = bound tuple minus its own signature. */
export function boundSignableBytes(b: BoundTransaction): string {
  const { binding_signature: _omit, ...rest } = b;
  return canonicalJson(rest);
}

export class BindingService {
  #nonces = new Map<string, NonceRecord>();
  #keys: KeyService;

  constructor(keys: KeyService) {
    this.#keys = keys;
  }

  bind(
    proposal: PaymentIntentProposal,
    delegation: Delegation,
    intentId: string,
    now: Date,
  ): BoundTransaction {
    const nonce = "nx_" + randomUUID().replace(/-/g, "");
    this.#nonces.set(nonce, {
      nonce,
      delegation_id: delegation.delegation_id,
      intent_id: intentId,
      expires_at: now.getTime() + NONCE_WINDOW_MS,
      consumed: false,
    });

    const draft: BoundTransaction = {
      intent_id: intentId,
      delegation_id: delegation.delegation_id,
      delegation_version: delegation.version,
      agent_id: delegation.agent.id,
      agent_pubkey: delegation.agent.pubkey,
      cart_hash: hashCanonical(proposal.cart),
      amount_paise: proposal.amount_paise,
      currency: proposal.currency,
      merchant: proposal.merchant,
      nonce,
      bound_at: now.toISOString(),
      binding_signature: "",
    };
    draft.binding_signature = this.#keys.sign(delegation.agent.key_id, boundSignableBytes(draft));
    return draft;
  }

  verifyBinding(b: BoundTransaction): boolean {
    return verifySignature(b.agent_pubkey, boundSignableBytes(b), b.binding_signature);
  }

  /** Fresh = exists, not expired, not yet consumed (used by CAN_PAY check 12). */
  isNonceFresh(nonce: string, now: Date): boolean {
    const rec = this.#nonces.get(nonce);
    if (!rec) return false;
    if (rec.consumed) return false;
    return now.getTime() <= rec.expires_at;
  }

  /** Single-use consumption at authorize time; a replay returns false. */
  consumeNonce(nonce: string, now: Date): boolean {
    const rec = this.#nonces.get(nonce);
    if (!rec || rec.consumed) return false;
    if (now.getTime() > rec.expires_at) return false;
    rec.consumed = true;
    return true;
  }
}
