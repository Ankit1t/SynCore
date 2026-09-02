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
  message_to_user: string;
}

export async function askAgent(text: string): Promise<DecideResponse> {
  const res = await fetch("/api/v1/agent/decide", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user_request: text, available_offers: "NONE" }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`agent request failed (${res.status})`);
  }
  return res.json();
}
