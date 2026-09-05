"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Wallet, Loader2, CheckCircle2, Download } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useWallet } from "@/components/wallet/WalletProvider";
import { downloadReceiptPdf } from "@/lib/receipt";
import type { DecideLine, OrderReceipt, ReceiptItem } from "@/lib/api";

const money = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

type Status = "idle" | "paying" | "paid" | "error";

function toItems(lines: DecideLine[]): ReceiptItem[] {
  return lines.map((l) => ({
    name: l.product_name,
    quantity: l.quantity,
    unit: l.unit,
    unit_price: l.unit_price,
    line_total: l.line_total,
  }));
}

/**
 * Fully-automated settlement: when an order is checkout-ready and the wallet is
 * funded, it is placed + paid from the wallet automatically, minting an
 * order_id and a downloadable PDF receipt. `autoPay` is true only for the
 * freshly-created order so revisiting history never re-charges.
 */
export function CheckoutButton({
  amountInr,
  orderId,
  autoPay,
  lines,
}: {
  amountInr: number;
  orderId: string;
  autoPay: boolean;
  lines: DecideLine[];
}) {
  const { wallet, loading, placeOrder, topUp, isPaid, markPaid } = useWallet();
  const [status, setStatus] = useState<Status>(() => (isPaid(orderId) ? "paid" : "idle"));
  const [note, setNote] = useState("");
  const [receipt, setReceipt] = useState<OrderReceipt | null>(null);
  const attempted = useRef(false);

  const balance = wallet?.balance_inr ?? null;
  const funded = balance != null && balance >= amountInr;
  const alreadyPaid = isPaid(orderId) || status === "paid";
  const topupAmt = balance == null ? 5000 : Math.max(500, Math.ceil((amountInr - balance) / 500) * 500);

  async function settle() {
    if (attempted.current) return;
    attempted.current = true;
    setStatus("paying");
    setNote("");
    const res = await placeOrder(toItems(lines));
    if (res.paid && res.receipt) {
      setReceipt(res.receipt);
      markPaid(orderId);
      setStatus("paid");
    } else {
      setStatus("error");
      setNote(res.reason === "insufficient balance" ? "insufficient wallet balance" : res.reason ?? "");
    }
  }

  useEffect(() => {
    if (autoPay && !alreadyPaid && funded && wallet && !attempted.current) {
      settle();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPay, funded, wallet, alreadyPaid]);

  if (alreadyPaid) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-4 rounded-xl border border-good/40 bg-good/10 p-3"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-good">
          <CheckCircle2 size={16} /> Order placed automatically — paid from wallet.
        </div>
        {receipt && (
          <>
            <div className="mt-2 flex items-center justify-between rounded-lg border border-good/30 bg-surface px-3 py-2 text-xs">
              <span className="text-muted">Order ID</span>
              <span className="font-mono font-semibold tabular-nums">{receipt.order_id}</span>
            </div>
            <Button
              variant="subtle"
              size="sm"
              onClick={() => downloadReceiptPdf(receipt)}
              className="mt-2 w-full"
            >
              <Download size={14} /> Download receipt (PDF)
            </Button>
          </>
        )}
        {!receipt && (
          <p className="mt-1 text-xs text-good/80">
            {wallet ? `Wallet balance: ${money(wallet.balance_inr)}` : "Paid from wallet."}
          </p>
        )}
      </motion.div>
    );
  }

  if (status === "paying") {
    return (
      <div className="mt-4 flex items-center gap-2 rounded-xl border border-line bg-elevated/50 p-3 text-sm text-primary">
        <Loader2 size={16} className="animate-spin text-accent" />
        Placing order & paying from wallet…
      </div>
    );
  }

  return (
    <div className="mt-4">
      {funded ? (
        <Button onClick={settle} className="w-full">
          <Wallet size={16} /> Pay {money(amountInr)} from Wallet
        </Button>
      ) : (
        <div className="space-y-2">
          <p className="rounded-xl border border-warn/40 bg-warn/10 p-3 text-xs text-warn">
            Wallet balance {balance != null ? money(balance) : "—"} is less than {money(amountInr)}.
          </p>
          <Button onClick={() => topUp(topupAmt)} disabled={loading} variant="subtle" className="w-full">
            {loading ? <Loader2 size={16} className="animate-spin" /> : `Top up ${money(topupAmt)} (test)`}
          </Button>
        </div>
      )}
      {status === "error" && note && (
        <p className="mt-1.5 text-xs text-bad">Payment failed: {note}.</p>
      )}
      <p className="mt-1.5 flex items-center gap-1 text-[11px] text-muted">
        <Wallet size={11} /> Orders settle instantly from your prepaid wallet — receipt with order ID.
      </p>
    </div>
  );
}
