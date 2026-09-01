/**
 * Provider Adapter interface (Blueprint 5.2, D3).
 *
 * Execution is certified commodity that SYNCCORE buys, never builds. Every PSP /
 * rail lives behind this adapter; only the Broker Orchestrator (Zone 2 scope)
 * ever holds provider credentials. Real adapters (Razorpay AutoPay, P3P) slot
 * in here without changing the control plane.
 */

import type { Paise } from "../domain/types.ts";

export type ProviderResult = "SUCCESS" | "FAILED" | "TIMEOUT";
export type ProviderStatus = "SUCCESS" | "FAILED" | "UNKNOWN" | "NOT_FOUND";

export interface ExecuteRequest {
  idempotency_key: string;
  amount_paise: Paise;
  currency: "INR";
  merchant: string;
  bound_ref: string; // cart hash / binding reference, for the provider's records
}

export interface ExecuteOutcome {
  result: ProviderResult;
  provider_ref: string | null;
}

export interface ProviderAdapter {
  readonly name: string;
  capabilities(): { autopay: boolean; refunds: boolean; sandbox: boolean };
  execute(req: ExecuteRequest): ExecuteOutcome;
  /** Ground-truth status used by reconciliation for UNKNOWN promotion. */
  status(providerRef: string): ProviderStatus;
}
