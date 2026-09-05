// Thin API client for the Syncore backend. In dev, next.config rewrites proxy
// /api/* to the FastAPI server, so we can use same-origin relative URLs.

export interface ParsedItem {
  canonical_name: string;
  requested_quantity: string;
  raw_text: string;
}

export interface BasketItem {
  canonical_name: string;
  title: string;
  packs: number;
  unit_price: number;
  line_total: number;
  reasons: string[];
}

export interface Basket {
  marketplace: string;
  objective: string;
  items: BasketItem[];
  items_subtotal: number;
  delivery_fee: number;
  platform_fee: number;
  discount: number;
  total: number;
  currency: string;
  within_budget: boolean;
  missing_items: string[];
  explanation: string[];
}

export interface Order {
  id: string;
  external_order_id: string | null;
  status: string;
  marketplace: string;
  vendor: string;
  total: number;
  currency: string;
  delivery_eta_minutes: number | null;
  items: Array<Record<string, unknown>>;
}

export interface Step {
  index: number;
  state: string;
  message: string;
  data: Record<string, unknown>;
}

export interface AgentRun {
  id: string;
  state: string;
  checkpoint_reason: string | null;
  error: Record<string, unknown> | null;
  steps: Step[];
  basket: Basket | null;
  order: Order | null;
}

export async function listOrders(): Promise<Order[]> {
  const res = await fetch("/api/v1/orders", { cache: "no-store" });
  if (!res.ok) throw new Error("failed to load orders");
  return res.json();
}

export async function getFeatureFlags(): Promise<Record<string, unknown>> {
  const res = await fetch("/api/v1/admin/feature-flags", { cache: "no-store" });
  return res.json();
}

// Open an SSE stream that runs the agent and yields events.
export function streamAgentRun(
  text: string,
  handlers: {
    onRequest?: (parsed: { items: ParsedItem[]; budget_limit: number | null }) => void;
    onStep?: (step: Step) => void;
    onFinal?: (run: AgentRun) => void;
    onError?: (message: string) => void;
  },
): () => void {
  const url = `/api/v1/shopping-requests/stream/live?text=${encodeURIComponent(text)}`;
  const es = new EventSource(url);

  // Guard so we only settle (and stop the spinner) once, and ignore the native
  // "error" event that fires when the server closes the stream after we finish.
  let settled = false;
  const finish = () => {
    settled = true;
    es.close();
  };

  es.addEventListener("request", (e) => handlers.onRequest?.(JSON.parse((e as MessageEvent).data)));
  es.addEventListener("step", (e) => handlers.onStep?.(JSON.parse((e as MessageEvent).data)));
  es.addEventListener("final", (e) => {
    if (settled) return;
    handlers.onFinal?.(JSON.parse((e as MessageEvent).data));
    finish();
  });
  // Application-level failure (parse error, agent error) carries a message.
  es.addEventListener("failure", (e) => {
    if (settled) return;
    let message = "Something went wrong. Please try again.";
    try {
      message = JSON.parse((e as MessageEvent).data).message || message;
    } catch {
      /* keep default */
    }
    handlers.onError?.(message);
    finish();
  });
  // Native EventSource error = connection problem (e.g. backend not running).
  es.addEventListener("error", () => {
    if (settled) return;
    handlers.onError?.(
      "Lost connection to the API. Make sure the backend is running on http://127.0.0.1:8000.",
    );
    finish();
  });

  return () => finish();
}

// --- Master Agent (any-item, LLM-powered) — /api/v1/agent/decide -----------

export interface DecideItem {
  raw: string;
  canonical: string;
  quantity: number | null;
  unit: string | null;
  confidence: number;
  brand?: string | null;
  variant_keywords?: string[];
}

export interface DecideReview {
  verdict: "PASS" | "PASS_WITH_NOTES" | "FAIL" | string;
  confidence: number;
  autopilot: "AUTO_EXECUTE" | "EXECUTE_NOTIFY" | "ASK_USER" | string;
  reasons: string[];
  concerns: string[];
  audit_id: string;
  question: string;
}

export interface DecideLine {
  offer_id: string;
  product_name: string;
  satisfies: string;
  quantity: number;
  unit: string;
  unit_price: number;
  line_total: number;
  estimated: boolean;
  reason: string;
  brand?: string | null;
  size_text?: string | null;
  image?: string | null;
  mrp?: number | null;
  rating?: number;
  seller_rating?: number;
  review_count?: number;
  eta_minutes?: number;
}

export interface DecideOption {
  option: string;
  action: string;
  resulting_total: number;
}

export interface DecideResponse {
  understanding: { budget_inr: number | null; items: DecideItem[]; notes: string };
  basket: { lines: DecideLine[]; total: number };
  budget_check: { within_budget: boolean; remaining_inr: number | null; over_by_inr: number | null };
  decisions: {
    substitutions: string[];
    quantity_changes: string[];
    dropped_items: string[];
    created_products: string[];
  };
  next_action: "PROCEED_TO_CHECKOUT" | "ASK_USER" | "RETRY_SEARCH" | string;
  options_for_user: DecideOption[];
  review?: DecideReview | null;
  message_to_user: string;
}

const DECIDE_PATH = "/api/v1/agent/decide";
const RENDER_ORIGIN = "https://syncore-api.onrender.com";
const LIVE_RENDER_DECIDE_URL = `${RENDER_ORIGIN}${DECIDE_PATH}`;

// --- Payments (Razorpay test mode) ---------------------------------------
export interface PaymentConfig {
  enabled: boolean;
  key_id?: string;
}
export interface CreatedOrder {
  enabled: boolean;
  ok?: boolean;
  order_id?: string;
  amount?: number;
  currency?: string;
  key_id?: string;
  reason?: string;
  error?: string;
}

async function paymentFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const isLocal =
    typeof window !== "undefined" &&
    (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");
  const urls = isLocal ? [path] : [path, `${RENDER_ORIGIN}${path}`];
  let lastError: unknown;
  for (const url of urls) {
    try {
      const res = await fetch(url, { cache: "no-store", ...init });
      if (!res.ok) throw new Error(`request failed (${res.status})`);
      return (await res.json()) as T;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("payment request failed");
}

export function getPaymentConfig(): Promise<PaymentConfig> {
  return paymentFetch<PaymentConfig>("/api/v1/pay/config");
}

export function createOrder(amountInr: number): Promise<CreatedOrder> {
  return paymentFetch<CreatedOrder>("/api/v1/pay/create-order", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ amount_inr: amountInr, receipt: "syncore-demo" }),
  });
}

// --- Wallet ---------------------------------------------------------------
export interface WalletTxn {
  id: string;
  type: "credit" | "debit";
  amount_inr: number;
  note: string;
  balance_after_inr: number;
  at: number;
}
export interface WalletState {
  balance_inr: number;
  currency: string;
  transactions: WalletTxn[];
}

export function getWallet(): Promise<WalletState> {
  return paymentFetch<WalletState>("/api/v1/wallet");
}

export function walletPay(
  amountInr: number,
  note = "Order",
): Promise<{ paid: boolean; balance_inr: number; reason?: string; shortfall_inr?: number; txn_id?: string }> {
  return paymentFetch("/api/v1/wallet/pay", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ amount_inr: amountInr, note }),
  });
}

export function walletTopupOrder(amountInr: number): Promise<CreatedOrder> {
  return paymentFetch<CreatedOrder>("/api/v1/wallet/topup-order", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ amount_inr: amountInr }),
  });
}

export function walletTopupConfirm(payload: {
  amount_inr: number;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}): Promise<{ ok: boolean; balance_inr?: number; reason?: string }> {
  return paymentFetch("/api/v1/wallet/topup-confirm", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// --- Product detail (view-only) ------------------------------------------
export interface ProductDetail {
  found: boolean;
  offer_id: string;
  product_name?: string;
  brand?: string | null;
  category?: string;
  unit_price?: number;
  mrp?: number | null;
  rating?: number;
  review_count?: number;
  in_stock?: boolean;
  image?: string | null;
  images?: string[];
  highlights?: string[];
  specifications?: Record<string, string>;
}

export function getProductDetail(offerId: string): Promise<ProductDetail> {
  return paymentFetch<ProductDetail>(`/api/v1/pdp/${encodeURIComponent(offerId)}`);
}

// --- Orders / receipts ----------------------------------------------------
export interface ReceiptItem {
  name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  line_total: number;
}
export interface OrderReceipt {
  order_id: string;
  placed_at: number;
  currency: string;
  items: ReceiptItem[];
  subtotal: number;
  total: number;
  payment_method: string;
  payment_status: string;
  wallet_balance_after: number;
}
export interface PlaceOrderResult {
  paid: boolean;
  order_id?: string;
  balance_inr?: number;
  receipt?: OrderReceipt;
  reason?: string;
  shortfall_inr?: number;
}

export function placeOrder(items: ReceiptItem[]): Promise<PlaceOrderResult> {
  return paymentFetch<PlaceOrderResult>("/api/v1/wallet/order", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ items }),
  });
}

export function verifyPayment(payload: {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}): Promise<{ verified: boolean }> {
  return paymentFetch<{ verified: boolean }>("/api/v1/pay/verify", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function requestDecision(
  url: string,
  text: string,
  availableOffers: string,
): Promise<DecideResponse> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user_request: text, available_offers: availableOffers }),
    cache: "no-store",
  });
  const contentType = res.headers.get("content-type") ?? "";
  if (!res.ok || !contentType.includes("application/json")) {
    throw new Error(`agent request failed (${res.status})`);
  }
  return res.json() as Promise<DecideResponse>;
}

export async function askAgent(
  text: string,
  opts: { live?: boolean } = {},
): Promise<DecideResponse> {
  const availableOffers = opts.live ? "LIVE" : "NONE";
  const isLocal =
    typeof window !== "undefined" &&
    (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

  // Normal path: same-origin Vercel rewrite. On production, fall back directly
  // to Render when that proxy returns a transient HTML/5xx response during a
  // free-tier cold start. `decide` is side-effect-free, so retrying is safe.
  const attempts = isLocal
    ? [DECIDE_PATH]
    : [DECIDE_PATH, LIVE_RENDER_DECIDE_URL, LIVE_RENDER_DECIDE_URL];
  let lastError: unknown;

  for (let i = 0; i < attempts.length; i += 1) {
    if (i > 0) await wait(i * 1_500);
    try {
      return await requestDecision(attempts[i], text, availableOffers);
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError instanceof Error ? lastError : new Error("agent request failed");
}

// --- AP2 Agentic Checkout (the "one door") --------------------------------

export interface AgenticConfig {
  provider: "razorpay" | "mock" | string;
  live_checkout: boolean;
  key_id: string;
  currency: string;
}

export interface PolicyCheck {
  name: string;
  passed: boolean;
  outcome: string | null;
  detail: string;
}

export interface PolicyDecisionView {
  outcome: "ALLOW" | "DENY" | "REQUIRES_USER_AUTHORIZATION" | string;
  rule_fired: string | null;
  checks: PolicyCheck[];
  reasons: string[];
  risk?: { level: string; reasons: string[] } | null;
}

export interface Ap2Mandate {
  mandate_type: string;
  mandate_id: string;
  content_digest: string;
  [key: string]: unknown;
}

export interface Ap2Chain {
  intent_mandate: Ap2Mandate;
  cart_mandate: Ap2Mandate & { cart_hash: string; total_amount: string; items: unknown[] };
  payment_mandate: (Ap2Mandate & { policy_outcome: string; amount: string }) | null;
}

export interface AgenticCheckoutResponse {
  stage:
    | "BASKET_NOT_PAYABLE"
    | "GATE_EVALUATED"
    | "BLOCKED"
    | "SETTLED"
    | "CHECKOUT_REQUIRED"
    | "PENDING_RECONCILE"
    | string;
  reason?: string;
  blocked_by?: string | null;
  agent_state?: string;
  request_id?: string;
  intent_id?: string;
  delegation_id?: string;
  basket?: Basket | null;
  cart?: Record<string, unknown>;
  decision?: PolicyDecisionView;
  ap2_mandates?: Ap2Chain;
  provider?: string;
  txn?: Record<string, unknown> | null;
  checkout_required?: boolean;
  checkout?: {
    provider: string;
    order_id: string;
    amount: number;
    currency: string;
    key_id: string;
    name: string;
    description: string;
    txn_id: string;
    intent_id: string;
  };
}

export interface AgenticConfirmResponse {
  verified: boolean;
  stage: string;
  txn?: Record<string, unknown> | null;
  receipt?: Record<string, unknown> | null;
  order_status?: string;
}

export function getAgenticConfig(): Promise<AgenticConfig> {
  return paymentFetch<AgenticConfig>("/api/v1/agentic/config");
}

export function agenticCheckout(body: {
  text: string;
  per_txn_paise?: number | null;
  daily_paise?: number | null;
  monthly_paise?: number | null;
  human_present?: boolean;
  payment_method?: string;
}): Promise<AgenticCheckoutResponse> {
  return paymentFetch<AgenticCheckoutResponse>("/api/v1/agentic/checkout", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function agenticConfirm(body: {
  intent_id: string;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}): Promise<AgenticConfirmResponse> {
  return paymentFetch<AgenticConfirmResponse>("/api/v1/agentic/confirm", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

// --- Agent Control Panel: delegations + kill switch -----------------------

export interface DelegationLimits {
  per_txn_paise: number;
  daily_paise: number;
  monthly_paise: number;
}

export interface Delegation {
  id: string;
  user_id: string;
  agent_id: string;
  purpose: string;
  allowed_categories: string[];
  allowed_merchants: string[];
  currency: string;
  limits: DelegationLimits;
  status: string;
  version: number;
  created_at: string;
  expires_at: string | null;
}

export function getAgenticMe(): Promise<{ user_id: string }> {
  return paymentFetch<{ user_id: string }>("/api/v1/agentic/me");
}

export function listDelegations(userId: string): Promise<Delegation[]> {
  return paymentFetch<Delegation[]>(`/api/v1/delegations?user_id=${encodeURIComponent(userId)}`);
}

export function createDelegation(body: {
  user_id: string;
  agent_id?: string;
  per_txn_paise: number;
  daily_paise: number;
  monthly_paise: number;
  allowed_categories: string[];
  allowed_merchants: string[];
  currency?: string;
}): Promise<Delegation> {
  return paymentFetch<Delegation>("/api/v1/delegations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function delegationAction(
  id: string,
  action: "revoke" | "pause" | "resume",
): Promise<Delegation> {
  return paymentFetch<Delegation>(`/api/v1/delegations/${id}/${action}`, { method: "POST" });
}

export function killSwitch(
  userId: string,
  mode: "pause-payments" | "resume-payments",
): Promise<{ paused?: number; resumed?: number; user_id: string }> {
  return paymentFetch(`/api/v1/agent/${mode}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
}

// --- Audit + Dispute ------------------------------------------------------

export interface AuditRow {
  intent_id: string;
  user_id: string;
  created_at: string;
  text: string;
  stage: string;
  decision_outcome: string | null;
  blocked_by: string | null;
  amount_paise: number | null;
  merchant_id: string | null;
}

export interface MandateCheck {
  digest_ok: boolean;
  link_ok: boolean;
  signature_ok: boolean;
  signer_id: string;
}

export interface AuditDetail {
  intent_id: string;
  user_id: string;
  created_at: string;
  text: string;
  stage: string;
  decision: PolicyDecisionView | null;
  ap2_mandates: Ap2Chain | null;
  verify_report: {
    chain_valid: boolean;
    intent_mandate?: MandateCheck;
    cart_mandate?: MandateCheck;
    payment_mandate?: MandateCheck;
  };
  txn: Record<string, unknown> | null;
  receipt: Record<string, unknown> | null;
}

export function listAudit(userId?: string): Promise<AuditRow[]> {
  const q = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return paymentFetch<AuditRow[]>(`/api/v1/agentic/audit${q}`);
}

export function getAuditDetail(intentId: string): Promise<AuditDetail> {
  return paymentFetch<AuditDetail>(`/api/v1/agentic/audit/${intentId}`);
}

// --- Merchant SDK verify --------------------------------------------------

export interface VerifyResult {
  ok: boolean;
  kind: string;
  report?: Record<string, unknown>;
  cart_hash?: string;
  total_amount?: string;
  error?: string;
}

export function verifyMandate(payload: unknown): Promise<VerifyResult> {
  return paymentFetch<VerifyResult>("/api/v1/agentic/verify-mandate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}
