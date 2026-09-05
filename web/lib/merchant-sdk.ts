/**
 * Syncore Merchant SDK (drop-in) — verify an AP2 mandate before you fulfil.
 * ---------------------------------------------------------------------------
 * A merchant receives a signed AP2 CartMandate (or the full intent->cart->payment
 * chain) from a shopping agent. Before shipping goods, the merchant verifies that:
 *   1. the chain links are intact (each mandate references the one above it), and
 *   2. every mandate's Ed25519 signature is valid (authoritative check).
 *
 * (1) is a pure, offline structural check done here in the browser/Node.
 * (2) is delegated to the Syncore verification endpoint, which does the
 *     cryptographic signature + canonical-digest verification server-side.
 *
 * Zero dependencies. Copy this file into any TS/JS project.
 *
 *   import { verifyMandate } from "./merchant-sdk";
 *   const result = await verifyMandate(cartMandateChain, { baseUrl: "https://your-syncore" });
 *   if (result.ok) fulfilOrder();
 */

export interface MandateLike {
  content_digest?: string;
  intent_mandate_ref?: string;
  cart_mandate_ref?: string;
  cart_hash?: string;
  total_amount?: string;
  signature?: string;
  signer_id?: string;
  [k: string]: unknown;
}

export interface MandateChainLike {
  intent_mandate?: MandateLike;
  cart_mandate?: MandateLike;
  payment_mandate?: MandateLike | null;
}

export interface VerifyOptions {
  /** Base URL of the Syncore backend. Defaults to same-origin (relative). */
  baseUrl?: string;
  /** Skip the server-side signature check and only run local link checks. */
  localOnly?: boolean;
}

export interface LocalCheck {
  links_ok: boolean;
  details: string[];
}

export interface MerchantVerifyResult {
  ok: boolean;
  local: LocalCheck;
  server?: {
    ok: boolean;
    kind: string;
    report?: Record<string, unknown>;
    cart_hash?: string;
    total_amount?: string;
    error?: string;
  };
  reason?: string;
}

/** Pure, offline: confirm the evidence chain references link up correctly. */
export function checkChainLinks(chain: MandateChainLike): LocalCheck {
  const details: string[] = [];
  let ok = true;

  const cart = chain.cart_mandate;
  const intent = chain.intent_mandate;
  const payment = chain.payment_mandate ?? undefined;

  if (!cart) {
    return { links_ok: false, details: ["missing cart_mandate"] };
  }
  if (!cart.signature) {
    ok = false;
    details.push("cart_mandate is not signed");
  }
  if (intent) {
    const linked = cart.intent_mandate_ref === intent.content_digest;
    if (!linked) {
      ok = false;
      details.push("cart_mandate.intent_mandate_ref does not match intent digest");
    } else {
      details.push("cart -> intent link OK");
    }
  }
  if (payment) {
    const linked = payment.cart_mandate_ref === cart.content_digest;
    if (!linked) {
      ok = false;
      details.push("payment_mandate.cart_mandate_ref does not match cart digest");
    } else {
      details.push("payment -> cart link OK");
    }
  }
  return { links_ok: ok, details };
}

/** Full verification: local link check + authoritative server signature check. */
export async function verifyMandate(
  chainOrCart: MandateChainLike | MandateLike,
  opts: VerifyOptions = {},
): Promise<MerchantVerifyResult> {
  const chain = ("cart_mandate" in chainOrCart
    ? (chainOrCart as MandateChainLike)
    : { cart_mandate: chainOrCart as MandateLike }) as MandateChainLike;

  const local = checkChainLinks(chain);

  if (opts.localOnly) {
    return { ok: local.links_ok, local };
  }

  const base = opts.baseUrl ?? "";
  try {
    const resp = await fetch(`${base}/api/v1/agentic/verify-mandate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(chainOrCart),
    });
    if (!resp.ok) {
      return { ok: false, local, reason: `verification service HTTP ${resp.status}` };
    }
    const server = (await resp.json()) as MerchantVerifyResult["server"];
    return { ok: Boolean(local.links_ok && server?.ok), local, server };
  } catch (e) {
    return { ok: false, local, reason: (e as Error).message };
  }
}
