import type { Basket, Order } from "@/lib/api";
import { objectiveLabel } from "@/lib/labels";
import { Pill } from "./Pill";

const money = (n: number) => `₹${(Math.round(n * 100) / 100).toLocaleString("en-IN")}`;

export function BasketCard({ basket, order }: { basket: Basket | null; order: Order | null }) {
  if (!basket) {
    return (
      <div className="py-6 text-center">
        <p className="text-sm font-medium text-white/90">Your recommended basket will appear here.</p>
        <p className="mt-1 text-xs text-muted">
          Once your agent finds the best options, you&apos;ll see the complete basket and total here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-muted">
        <span>
          From <span className="text-white/90">{basket.marketplace}</span>
        </span>
        <span aria-hidden="true">·</span>
        <span>{objectiveLabel(basket.objective)}</span>
        <Pill
          label={basket.within_budget ? "Within budget" : "Over budget"}
          tone={basket.within_budget ? "bg-good/15 text-good" : "bg-bad/15 text-bad"}
        />
      </div>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-xs text-muted">
            <th className="border-b border-line p-1.5 text-left">Item</th>
            <th className="border-b border-line p-1.5 text-right">Qty</th>
            <th className="border-b border-line p-1.5 text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {basket.items.map((i) => (
            <tr key={i.title}>
              <td className="border-b border-line p-1.5">
                <span className="text-white/90">{i.title}</span>
                {i.reasons.length > 0 && (
                  <span className="mt-0.5 block text-xs text-muted">{i.reasons.join(" · ")}</span>
                )}
              </td>
              <td className="border-b border-line p-1.5 text-right tabular-nums">×{i.packs}</td>
              <td className="border-b border-line p-1.5 text-right tabular-nums">{money(i.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 space-y-1 text-sm">
        <Row label="Subtotal" value={money(basket.items_subtotal)} />
        <Row label="Delivery" value={basket.delivery_fee ? money(basket.delivery_fee) : "Free"} />
        {basket.platform_fee > 0 && <Row label="Platform fee" value={money(basket.platform_fee)} />}
        {basket.discount > 0 && <Row label="Discount" value={`−${money(basket.discount)}`} />}
        <div className="mt-1.5 flex justify-between border-t border-line pt-2.5 text-[17px] font-extrabold tabular-nums">
          <span>Total</span>
          <span>{money(basket.total)}</span>
        </div>
      </div>

      <p className={`mt-2 text-sm ${basket.within_budget ? "text-good" : "text-bad"}`}>
        {basket.within_budget ? "✓ Within your budget" : "This basket is over your budget."}
      </p>

      {order && (
        <div className="card mt-4 bg-panel2 p-4">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Order</h4>
          <div className="flex items-center gap-2">
            <Pill label={order.status} />
            <b className="tabular-nums">{order.external_order_id || "—"}</b>
          </div>
          <div className="mt-1.5 text-sm text-muted">
            {order.vendor} · {money(order.total)}
            {order.delivery_eta_minutes ? ` · arrives in ~${order.delivery_eta_minutes} min` : ""}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}
