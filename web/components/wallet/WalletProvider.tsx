"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  getWallet,
  walletPay,
  walletTopupOrder,
  walletTopupConfirm,
  type WalletState,
} from "@/lib/api";
import { openCheckout } from "@/lib/razorpay";

interface WalletContextValue {
  wallet: WalletState | null;
  loading: boolean;
  refresh: () => Promise<void>;
  payFromWallet: (
    amountInr: number,
    note?: string,
  ) => Promise<{ paid: boolean; reason?: string; shortfall_inr?: number }>;
  topUp: (amountInr: number) => Promise<{ ok: boolean; reason?: string }>;
}

const WalletContext = createContext<WalletContextValue | null>(null);

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [wallet, setWallet] = useState<WalletState | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setWallet(await getWallet());
    } catch {
      /* keep last known */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const payFromWallet = useCallback(
    async (amountInr: number, note = "Order") => {
      setLoading(true);
      try {
        const res = await walletPay(amountInr, note);
        if (typeof res.balance_inr === "number") {
          setWallet((w) => (w ? { ...w, balance_inr: res.balance_inr } : w));
        }
        await refresh();
        return { paid: res.paid, reason: res.reason, shortfall_inr: res.shortfall_inr };
      } finally {
        setLoading(false);
      }
    },
    [refresh],
  );

  const topUp = useCallback(
    async (amountInr: number) => {
      setLoading(true);
      try {
        const order = await walletTopupOrder(amountInr);
        if (!order.enabled) return { ok: false, reason: "Payment not configured on server" };
        if (!order.ok || !order.order_id || !order.key_id) {
          return { ok: false, reason: order.error || "could not create top-up order" };
        }
        const resp = await openCheckout({
          key: order.key_id,
          amount: order.amount ?? amountInr * 100,
          currency: order.currency ?? "INR",
          orderId: order.order_id,
          name: "SynCore Wallet",
          description: `Add ₹${amountInr} to wallet (test)`,
        });
        const confirmed = await walletTopupConfirm({ amount_inr: amountInr, ...resp });
        await refresh();
        return { ok: Boolean(confirmed.ok), reason: confirmed.reason };
      } catch (e) {
        return { ok: false, reason: e instanceof Error ? e.message : "top-up failed" };
      } finally {
        setLoading(false);
      }
    },
    [refresh],
  );

  return (
    <WalletContext.Provider value={{ wallet, loading, refresh, payFromWallet, topUp }}>
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet(): WalletContextValue {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error("useWallet must be used within WalletProvider");
  return ctx;
}
