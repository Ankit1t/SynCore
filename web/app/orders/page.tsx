"use client";

import { useEffect, useState } from "react";
import { Pill } from "@/components/Pill";
import { listOrders, type Order } from "@/lib/api";

const money = (n: number) => `₹${(Math.round(n * 100) / 100).toLocaleString("en-IN")}`;

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listOrders()
      .then(setOrders)
      .catch(() => setError("We couldn't load your orders right now. Please try again."));
  }, []);

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Orders</h2>
      {error && (
        <p role="alert" className="rounded-lg border border-bad/40 bg-bad/10 p-3 text-sm text-bad">
          {error}
        </p>
      )}
      {orders.length === 0 && !error && (
        <div className="py-6 text-center">
          <p className="text-sm font-medium text-white/90">No orders yet.</p>
          <p className="mt-1 text-xs text-muted">Orders your agent completes will appear here.</p>
        </div>
      )}
      <div className="space-y-3">
        {orders.map((o) => (
          <div key={o.id} className="card flex items-center justify-between p-4">
            <div>
              <div className="flex items-center gap-2">
                <Pill label={o.status} />
                <b>{o.external_order_id || o.id.slice(0, 8)}</b>
              </div>
              <div className="mt-1 text-sm text-muted">
                {o.marketplace} · {o.items.length} item(s) · ETA ~{o.delivery_eta_minutes} min
              </div>
            </div>
            <div className="text-lg font-bold">{money(o.total)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
