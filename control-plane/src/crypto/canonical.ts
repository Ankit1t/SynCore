/**
 * Canonical JSON + SHA-256.
 *
 * Signatures and the cart hash must be computed over a byte-stable encoding, so
 * we serialize with recursively sorted object keys and no incidental
 * whitespace. This is the canonicalization referenced by W3 (cart hash) and by
 * every signed artifact.
 */

import { createHash } from "node:crypto";

export function canonicalJson(value: unknown): string {
  return JSON.stringify(sortDeep(value));
}

function sortDeep(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortDeep);
  }
  if (value !== null && typeof value === "object") {
    const src = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(src).sort()) {
      out[key] = sortDeep(src[key]);
    }
    return out;
  }
  return value;
}

export function sha256Hex(input: string): string {
  return createHash("sha256").update(input, "utf8").digest("hex");
}

/** SHA-256 over the canonical JSON of a value (used for cart hashing). */
export function hashCanonical(value: unknown): string {
  return sha256Hex(canonicalJson(value));
}
