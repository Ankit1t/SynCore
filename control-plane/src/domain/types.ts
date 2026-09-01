/**
 * Frozen domain types (Blueprint v1.0, chapters 5-8).
 *
 * Erasable-only TypeScript (no enums/namespaces) so Node can run these .ts
 * files directly via type-stripping. State sets are const maps + union types.
 *
 * All money is integer paise. All timestamps are ISO-8601 UTC strings.
 */

export type Paise = number;

// --- Policy outcomes ---------------------------------------------------------
export type Decision = "ALLOW" | "CHALLENGE" | "DENY";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

// --- Delegation --------------------------------------------------------------
export type DelegationStatus = "ACTIVE" | "SUSPENDED" | "REVOKED" | "EXPIRED";
export type SubstitutionPolicy = "ASK" | "NEVER" | "AUTO";

export interface MerchantScope {
  mode: "allowlist" | "category";
  merchants: string[];
}

export interface Limits {
  per_tx: Paise;
  daily: Paise;
  weekly: Paise;
  monthly: Paise;
}

export interface UserSignature {
  alg: "Ed25519";
  key: string; // passkey / WebAuthn public key ref ("webauthn:<pubkey>")
  over: string; // canonical bytes that were signed
  sig: string; // base64 signature
}

export interface Delegation {
  delegation_id: string;
  version: number;
  principal: string; // user id
  agent: { id: string; key_id: string; pubkey: string };
  purpose: string;
  merchant_scope: MerchantScope;
  category_scope: string[];
  limits_paise: Limits;
  currency: "INR";
  price_drift_bps: number;
  substitution: SubstitutionPolicy;
  require_confirmation_above_paise: Paise;
  valid_from: string;
  expires_at: string;
  nonce: string;
  status: DelegationStatus;
  user_signature?: UserSignature;
}

// --- Proposal (the ONLY thing Zone 0 may emit toward money) ------------------
export interface CartLine {
  sku: string;
  qty: number;
  unit_paise: Paise;
}

export interface PaymentIntentProposal {
  purpose: string;
  merchant: string;
  category: string;
  cart: CartLine[];
  amount_paise: Paise;
  currency: "INR";
}

/** A fresh, user-signed confirmation for CHALLENGE flows (check 10). */
export interface UserConfirmation {
  over: string; // canonical bytes (intent id + amount + merchant)
  sig: string; // base64 signature by the user's passkey
  key: string; // user passkey pubkey ref
  issued_at: string;
}

// --- Ledger view consumed by CAN_PAY (velocity check) ------------------------
export interface LedgerView {
  spent_daily_paise: Paise;
  spent_weekly_paise: Paise;
  spent_monthly_paise: Paise;
}

// --- Agent proof (DPoP-style, bound to the agent key) ------------------------
export interface AgentProof {
  agent_id: string;
  key_id: string;
  over: string; // canonical bytes (method + path + intent context)
  sig: string; // base64 signature by the agent key
}

// --- Cryptographic binding (W3) ---------------------------------------------
export interface BoundTransaction {
  intent_id: string;
  delegation_id: string;
  delegation_version: number;
  agent_id: string;
  agent_pubkey: string;
  cart_hash: string; // sha256(canonical(cart))
  amount_paise: Paise;
  currency: "INR";
  merchant: string;
  nonce: string;
  bound_at: string;
  binding_signature: string; // agent-signed over canonical(bound tuple minus signature)
}

// --- Risk (W5 v0) ------------------------------------------------------------
export interface RiskVerdict {
  level: RiskLevel;
  signals: Record<string, number | string | boolean>;
  reason: string;
}

// --- CAN_PAY() decision record ----------------------------------------------
export interface CheckResult {
  index: number;
  name: string;
  passed: boolean;
  outcome: Decision | "PASS";
  detail: string;
}

export interface CanPayDecision {
  decision: Decision;
  rule_fired: string | null; // earliest failing / challenging rule
  checks: CheckResult[];
  risk: RiskVerdict;
  decided_at: string;
}

// --- Payment execution -------------------------------------------------------
export type PaymentState =
  | "PENDING"
  | "EXECUTING"
  | "SUCCESS"
  | "FAILED"
  | "UNKNOWN"
  | "SETTLED"
  | "DROPPED";

export type PaymentEvent =
  | "EXECUTE"
  | "PROVIDER_SUCCESS"
  | "PROVIDER_FAILED"
  | "PROVIDER_TIMEOUT"
  | "RECON_SETTLED"
  | "RECON_DROPPED"
  | "FINALIZE";

export interface PaymentResult {
  intent_id: string;
  state: PaymentState;
  provider: string;
  provider_ref: string | null;
  amount_paise: Paise;
  detail: string;
}

// --- Audit ledger (W7) -------------------------------------------------------
export interface AuditEvent {
  seq: number;
  at: string;
  actor: string;
  type: string;
  intent_id: string | null;
  payload: unknown;
  prev_hash: string;
  entry_hash: string;
}

export interface ProofBundle {
  intent_id: string;
  events: AuditEvent[];
  chain_valid: boolean;
}
