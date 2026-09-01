/**
 * Delegation Service (Blueprint 5.2, 6, W1).
 *
 * Owns the delegation lifecycle: creation (user WebAuthn ceremony over canonical
 * bytes), suspend/resume (versioned, re-auth on resume), and revoke (terminal,
 * server-authoritative and immediate). Revocation is evaluated server-side at
 * decision time; an agent's local cached view is never trusted for freshness
 * (the 5s propagation cap in the blueprint bounds only that stale local view).
 */

import { randomUUID } from "node:crypto";
import { type Clock, systemClock } from "../domain/clock.ts";
import { canonicalJson } from "../crypto/canonical.ts";
import { UserPasskey } from "../crypto/keys.ts";
import type { AuditLedger } from "../ledger/audit.ts";
import type {
  Delegation,
  DelegationStatus,
  Limits,
  MerchantScope,
  SubstitutionPolicy,
} from "../domain/types.ts";

export interface CreateDelegationInput {
  principal: string;
  agent: { id: string; key_id: string; pubkey: string };
  purpose: string;
  merchant_scope: MerchantScope;
  category_scope: string[];
  limits_paise: Limits;
  price_drift_bps: number;
  substitution: SubstitutionPolicy;
  require_confirmation_above_paise: number;
  valid_from?: string;
  expires_at: string;
}

/**
 * Bytes the user signs = the immutable authority grant. We exclude the
 * signature itself AND the mutable `status`, because lifecycle transitions
 * (suspend/resume/revoke) are separate signed events (Blueprint Fig 6.1), not
 * re-signings of the original artifact. Everything that defines *authority*
 * (limits, scope, agent, validity, drift, nonce, version) is covered.
 */
export function delegationSignableBytes(d: Delegation): string {
  const { user_signature: _sig, status: _status, ...rest } = d;
  return canonicalJson(rest);
}

export class DelegationService {
  #current = new Map<string, Delegation>();
  #history = new Map<string, Delegation[]>();
  #ledger: AuditLedger;
  #clock: Clock;

  constructor(ledger: AuditLedger, clock: Clock = systemClock) {
    this.#ledger = ledger;
    this.#clock = clock;
  }

  createDelegation(input: CreateDelegationInput, userKey: UserPasskey): Delegation {
    const now = this.#clock().toISOString();
    const draft: Delegation = {
      delegation_id: "dlg_" + randomUUID().replace(/-/g, "").slice(0, 22),
      version: 1,
      principal: input.principal,
      agent: input.agent,
      purpose: input.purpose,
      merchant_scope: input.merchant_scope,
      category_scope: input.category_scope,
      limits_paise: input.limits_paise,
      currency: "INR",
      price_drift_bps: input.price_drift_bps,
      substitution: input.substitution,
      require_confirmation_above_paise: input.require_confirmation_above_paise,
      valid_from: input.valid_from ?? now,
      expires_at: input.expires_at,
      nonce: "n_" + randomUUID().replace(/-/g, "").slice(0, 16),
      status: "ACTIVE",
    };
    const over = delegationSignableBytes(draft);
    draft.user_signature = { alg: "Ed25519", key: userKey.pubkey, over, sig: userKey.sign(over) };

    this.#store(draft);
    this.#ledger.append("user:" + input.principal, "DELEGATION_CREATED", null, {
      delegation_id: draft.delegation_id,
      version: draft.version,
      agent: draft.agent.id,
      limits_paise: draft.limits_paise,
    });
    return draft;
  }

  /** Verify the user signature over the artifact's canonical bytes. */
  verifyUserSignature(d: Delegation): boolean {
    if (!d.user_signature) return false;
    const over = delegationSignableBytes(d);
    if (over !== d.user_signature.over) return false; // artifact was altered post-signing
    return UserPasskey.verify(d.user_signature.key, over, d.user_signature.sig);
  }

  get(id: string): Delegation | undefined {
    return this.#current.get(id);
  }

  /** Effective status accounting for expiry against the authoritative clock. */
  effectiveStatus(d: Delegation): DelegationStatus {
    if (d.status === "REVOKED" || d.status === "SUSPENDED") return d.status;
    const now = this.#clock().getTime();
    if (now < Date.parse(d.valid_from) || now >= Date.parse(d.expires_at)) return "EXPIRED";
    return d.status;
  }

  suspend(id: string, requestedBy: string): Delegation {
    const d = this.#require(id);
    if (d.status === "REVOKED") throw new Error("cannot suspend a revoked delegation");
    d.status = "SUSPENDED";
    this.#ledger.append(requestedBy, "DELEGATION_SUSPENDED", null, { delegation_id: id });
    return d;
  }

  /** Resume requires a fresh user re-authentication (new signature, version+1). */
  resume(id: string, userKey: UserPasskey): Delegation {
    const prev = this.#require(id);
    if (prev.status !== "SUSPENDED") throw new Error("only suspended delegations can resume");
    const next: Delegation = { ...prev, version: prev.version + 1, status: "ACTIVE" };
    delete next.user_signature;
    const over = delegationSignableBytes(next);
    next.user_signature = { alg: "Ed25519", key: userKey.pubkey, over, sig: userKey.sign(over) };
    this.#store(next);
    this.#ledger.append("user:" + prev.principal, "DELEGATION_RESUMED", null, {
      delegation_id: id,
      version: next.version,
    });
    return next;
  }

  revoke(id: string, reason: string, requestedBy: string): Delegation {
    const d = this.#require(id);
    d.status = "REVOKED";
    this.#ledger.append(requestedBy, "DELEGATION_REVOKED", null, { delegation_id: id, reason });
    return d;
  }

  history(id: string): readonly Delegation[] {
    return this.#history.get(id) ?? [];
  }

  #store(d: Delegation): void {
    this.#current.set(d.delegation_id, d);
    const h = this.#history.get(d.delegation_id) ?? [];
    h.push(structuredClone(d));
    this.#history.set(d.delegation_id, h);
  }

  #require(id: string): Delegation {
    const d = this.#current.get(id);
    if (!d) throw new Error(`unknown delegation: ${id}`);
    return d;
  }
}
