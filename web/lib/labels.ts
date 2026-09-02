// Presentation-layer copy for Syncore. Maps the REAL backend agent states and
// objectives (from the existing orchestrator state machine) into polished,
// user-facing labels. This does not create a second state system — it only
// renames the states the backend already emits.

// Raw agent state (from the orchestrator) -> friendly label shown to the user.
const STATE_LABEL: Record<string, string> = {
  REQUEST_RECEIVED: "Received your request",
  INTENT_PARSED: "Understanding your request",
  PLAN_CREATED: "Planning your order",
  SEARCHING: "Finding products",
  DISCOVERING_PRODUCTS: "Finding products",
  EXTRACTING_PRODUCTS: "Reading product details",
  NORMALIZING: "Comparing options",
  RANKING: "Comparing prices",
  OPTIMIZING: "Optimizing your basket",
  BASKET_READY: "Basket ready",
  USER_REVIEW_REQUIRED: "Needs your review",
  BROWSER_SESSION_STARTED: "Opening a secure shopping session",
  SEARCH_EXECUTION: "Searching the store",
  PRODUCT_SELECTED: "Selecting products",
  CART_BUILDING: "Building your cart",
  CART_VERIFIED: "Cart verified",
  CHECKOUT_READY: "Preparing checkout",
  PAYMENT_PENDING: "Preparing payment",
  PAYMENT_AUTH_REQUIRED: "Awaiting your authorization",
  PAYMENT_PROCESSING: "Placing the order",
  ORDER_PLACED: "Order placed",
  ORDER_VERIFICATION: "Confirming your order",
  COMPLETED: "Completed",
  FAILED: "Couldn't complete",
  RECOVERY: "Recovering",
  CANCELLED: "Cancelled",
  ERROR: "Something went wrong",
  // Master-agent next actions
  PROCEED_TO_CHECKOUT: "Ready to checkout",
  ASK_USER: "Needs your review",
  RETRY_SEARCH: "No suitable products found",
  READY: "Ready",
};

export function stateLabel(state: string): string {
  return (
    STATE_LABEL[state] ??
    state
      .toLowerCase()
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

// States that represent a finished/terminal outcome for the run.
const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED", "ERROR", "USER_REVIEW_REQUIRED", "PAYMENT_AUTH_REQUIRED"]);
export function isTerminalState(state: string): boolean {
  return TERMINAL.has(state);
}

const OBJECTIVE_LABEL: Record<string, string> = {
  BEST_VALUE: "Best value",
  CHEAPEST: "Lowest price",
  FASTEST: "Fastest delivery",
  BEST_QUALITY: "Best quality",
  BALANCED: "Balanced",
};

export function objectiveLabel(objective: string): string {
  return OBJECTIVE_LABEL[objective] ?? objective;
}

// Turn a raw error/message into safe, user-facing copy (never leak internals).
export function friendlyError(message: string | undefined | null): string {
  const m = (message ?? "").trim();
  if (!m) return "Something went wrong while processing your request. Please try again.";
  const lower = m.toLowerCase();
  if (lower.includes("connection") || lower.includes("backend")) {
    return "We can't reach the agent service right now. Please make sure it's running and try again.";
  }
  if (lower.includes("grocery items") || lower.includes("recognize")) {
    return m; // already a friendly, actionable message from the agent
  }
  if (lower.includes("budget")) {
    return "No combination matching your requirements was found within your budget.";
  }
  // Never surface stack traces / exception text.
  if (/(traceback|exception|error:|at\s+\w+\.py|<.*object.*>)/i.test(m)) {
    return "Something went wrong while processing your request. Please try again.";
  }
  return m;
}
