"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Wallet, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useWallet } from "@/components/wallet/WalletProvider";

const money = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

type Status = "idle" | "paying" | "paid" | "error";

/**
 * Fully-automated settlement. When an order is checkout-ready and the wallet
 * has funds, it is paid automatically from the prepaid wallet — no click, no
 * gateway step. `autoPay` is true only for the freshly-created order so that
 * revisiting history never re-charges.
 */
export function CheckoutButton({
  amountInr,
  orderId,
  autoPay,
}: {
  amountInr: number;
  orderId: string;
  autoPay: boolean;
}) {
  const { wallet, loading, payFromWallet, topUp, isPaid, markPaid } = useWallet();
  const [status, setStatus] = useState<Status>(() => (isPaid(orderId) ? "paid" : "idle"));
  const [note, setNote] = useState("");
  const attempted = useRef(false);

  const balance = wallet?.balance_inr ?? null;
  const funded = balance != null && balance >= amountInr;
  const alreadyPaid = isPaid(orderId) || status === "paid";

  async function settle() {
    if (attempted.current) return;
    attempted.current = true;
    setStatus("paying");
    setNote("");
    const res = await payFromWallet(amountInr, "SynCore order (auto)");
    if (res.paid) {
      markPaid(orderId);
      setStatus("paid");
    } else {
      setStatus("error");
      setNote(res.reason === "insufficient balance" ? "insufficient wallet balance" : res.reason ?? "");
    }
  }

  // Auto-settle the freshly-created order as soon as the wallet is funded.
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
        className="mt-4 rounded-xl border border-good/40 bg-good/10 p-3 text-sm text-good"
      >
        <div className="flex items-center gap-2 font-medium">
          <CheckCircle2 size={16} /> Order placed automatically — paid from wallet.
        </div>
        {wallet && (
          <p className="mt-1 text-xs text-good/80">
            No payment step. Wallet balance: {money(wallet.balance_inr)}
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

  // Not funded (or auto-pay failed) -> ask the user to top up (amount entered in the header).
  return (
    <div className="mt-4">
      {funded ? (
        <Button onClick={settle} disabled={status === "error" && loading} className="w-full">
          <Wallet size={16} /> Pay {money(amountInr)} from Wallet
        </Button>
      ) : (
        <div className="rounded-xl border border-warn/40 bg-warn/10 p-3 text-xs text-warn">
          Wallet balance {balance != null ? money(balance) : "—"} is less than {money(amountInr)}.
          Add money using the <span className="font-semibold">wallet top-up</span> in the header,
          then the order settles automatically.
        </div>
      )}
      {status === "error" && note && (
        <p className="mt-1.5 text-xs text-bad">Payment failed: {note}.</p>
      )}
      <p className="mt-1.5 flex items-center gap-1 text-[11px] text-muted">
        <Wallet size={11} /> Orders settle instantly from your prepaid wallet — no gateway step.
      </p>
    </div>
  );
}
