import type { DecideResponse } from "@/lib/api";
import { Pill } from "./Pill";

const money = (n: number) => `₹${(Math.round(n * 100) / 100).toLocaleString("en-IN")}`;

function qtyLabel(quantity: number, unit: string): string {
  const q = Number.isInteger(quantity) ? quantity : Math.round(quantity * 100) / 100;
  return `${q} ${unit}`;
}

export function DecideBasket({ result }: { result: DecideResponse | null }) {
  if (!result || result.basket.lines.length === 0) {
    return (
      <div className="py-6 text-center">
        <p className="text-sm font-medium text-white/90">Your recommended basket will appear here.</p>
        <p className="mt-1 text-xs text-muted">
          Ask for anything — groceries, snacks, electronics — and the agent builds the basket within
          your budget.
        </p>
      </div>
    );
  }

  const b = result.basket;
  const bc = result.budget_check;
  const hasEstimates = b.lines.some((l) => l.estimated);

  return (
    <div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-xs text-muted">
            <th className="border-b border-line p-1.5 text-left">Item</th>
            <th className="border-b border-line p-1.5 text-right">Qty</th>
            <th className="border-b border-line p-1.5 text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {b.lines.map((l) => (
            <tr key={l.offer_id}>
              <td className="border-b border-line p-1.5">
                <span className="text-white/90">{l.product_name}</span>
                {l.estimated && (
                  <span className="ml-2 rounded bg-warn/15 px-1.5 py-0.5 text-[10px] font-semibold text-warn">
                    est. price
                  </span>
                )}
              </td>
              <td className="border-b border-line p-1.5 text-right tabular-nums">
                {qtyLabel(l.quantity, l.unit)}
              </td>
              <td className="border-b border-line p-1.5 text-right tabular-nums">{money(l.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center justify-between border-t border-line pt-2.5 text-[17px] font-extrabold tabular-nums">
        <span>Total</span>
        <span>{money(b.total)}</span>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <Pill
          label={bc.within_budget ? "Within budget" : "Over budget"}
          tone={bc.within_budget ? "bg-good/15 text-good" : "bg-bad/15 text-bad"}
        />
        {result.understanding.budget_inr != null && (
          <span className="text-xs text-muted">
            Budget {money(result.understanding.budget_inr)}
            {bc.within_budget && bc.remaining_inr != null
              ? ` · ${money(bc.remaining_inr)} left`
              : bc.over_by_inr != null
                ? ` · ${money(bc.over_by_inr)} over`
                : ""}
          </span>
        )}
      </div>

      {hasEstimates && (
        <p className="mt-2 text-xs text-muted">
          Prices marked “est.” are the agent’s market estimates (no live retail price source
          connected yet).
        </p>
      )}

      {result.options_for_user.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">Options</p>
          <ul className="space-y-1 text-sm">
            {result.options_for_user.map((o) => (
              <li key={o.option} className="flex justify-between gap-3">
                <span className="text-white/90">{o.option}</span>
                <span className="tabular-nums text-muted">{money(o.resulting_total)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
