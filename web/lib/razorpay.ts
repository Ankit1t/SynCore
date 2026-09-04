// Shared Razorpay hosted-checkout loader + promisified open.

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

export interface RazorpayResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

const CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

export function loadRazorpay(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") return resolve(false);
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = CHECKOUT_SRC;
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

/** Opens Razorpay checkout; resolves with the signed response, rejects on dismiss/failure. */
export async function openCheckout(opts: {
  key: string;
  amount: number;
  currency: string;
  orderId: string;
  name: string;
  description: string;
}): Promise<RazorpayResponse> {
  const ok = await loadRazorpay();
  if (!ok || !window.Razorpay) throw new Error("could not load checkout");
  return new Promise<RazorpayResponse>((resolve, reject) => {
    const rzp = new window.Razorpay!({
      key: opts.key,
      amount: opts.amount,
      currency: opts.currency,
      name: opts.name,
      description: opts.description,
      order_id: opts.orderId,
      theme: { color: "#6366f1" },
      handler: (resp: RazorpayResponse) => resolve(resp),
      modal: { ondismiss: () => reject(new Error("cancelled")) },
    });
    rzp.open();
  });
}
