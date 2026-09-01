/**
 * Key Service (Blueprint 5.2 / W4).
 *
 * In production, agent Ed25519 private keys are generated inside a cloud KMS
 * with HSM backing and are NON-EXPORTABLE (freeze decision D4). This module is
 * the same interface with an in-memory key store for Phase 0 sandbox: private
 * keys never leave this service, callers only ever hold a `key_id` and the
 * public key. Swapping to KMS is an adapter change, not an interface change.
 */

import {
  createPrivateKey,
  createPublicKey,
  generateKeyPairSync,
  randomUUID,
  sign as edSign,
  verify as edVerify,
  type KeyObject,
} from "node:crypto";

export interface AgentKeyHandle {
  key_id: string;
  pubkey: string; // "ed25519:<base64 spki der>"
}

const PREFIX = "ed25519:";

export function encodePublicKey(pub: KeyObject): string {
  const der = pub.export({ type: "spki", format: "der" });
  return PREFIX + der.toString("base64");
}

export function decodePublicKey(pubkey: string): KeyObject {
  if (!pubkey.startsWith(PREFIX)) {
    throw new Error("unsupported public key format");
  }
  const der = Buffer.from(pubkey.slice(PREFIX.length), "base64");
  return createPublicKey({ key: der, format: "der", type: "spki" });
}

/** Stateless verify usable anywhere (the gate verifies proofs/signatures). */
export function verifySignature(pubkey: string, message: string, sigBase64: string): boolean {
  try {
    const pub = decodePublicKey(pubkey);
    return edVerify(null, Buffer.from(message, "utf8"), pub, Buffer.from(sigBase64, "base64"));
  } catch {
    return false; // malformed input fails closed
  }
}

export class KeyService {
  // key_id -> non-exportable private key (KMS-resident in production)
  #store = new Map<string, KeyObject>();

  /** Generate a fresh agent key pair; the private key stays inside the service. */
  generateAgentKey(): AgentKeyHandle {
    const { publicKey, privateKey } = generateKeyPairSync("ed25519");
    const keyId = "agpk_" + randomUUID().replace(/-/g, "").slice(0, 20);
    this.#store.set(keyId, privateKey);
    return { key_id: keyId, pubkey: encodePublicKey(publicKey) };
  }

  sign(keyId: string, message: string): string {
    const priv = this.#store.get(keyId);
    if (!priv) throw new Error(`unknown key_id: ${keyId}`);
    return edSign(null, Buffer.from(message, "utf8"), priv).toString("base64");
  }

  hasKey(keyId: string): boolean {
    return this.#store.has(keyId);
  }
}

/**
 * Simulated user passkey (WebAuthn ceremony). In production the user's secret
 * never exists on any server; here we model the signing ceremony so delegation
 * artifacts and confirmations are genuinely verifiable end to end.
 */
export class UserPasskey {
  #priv: KeyObject;
  readonly pubkey: string;

  constructor() {
    const { publicKey, privateKey } = generateKeyPairSync("ed25519");
    this.#priv = privateKey;
    this.pubkey = "webauthn:" + encodePublicKey(publicKey).slice(PREFIX.length);
  }

  sign(message: string): string {
    return edSign(null, Buffer.from(message, "utf8"), this.#priv).toString("base64");
  }

  static verify(pubkeyRef: string, message: string, sigBase64: string): boolean {
    const raw = pubkeyRef.startsWith("webauthn:") ? pubkeyRef.slice("webauthn:".length) : pubkeyRef;
    return verifySignature(PREFIX + raw, message, sigBase64);
  }
}

export function toDer(privatePem: string): KeyObject {
  return createPrivateKey(privatePem);
}
