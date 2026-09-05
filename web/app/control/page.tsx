"use client";

import { useEffect, useState } from "react";
import {
  ShieldCheck,
  Plus,
  Pause,
  Play,
  Ban,
  Power,
  Loader2,
  RefreshCw,
} from "lucide-react";
import {
  createDelegation,
  delegationAction,
  getAgenticMe,
  killSwitch,
  listDelegations,
  type Delegation,
} from "@/lib/api";

const rupees = (paise: number) => `₹${(paise / 100).toLocaleString("en-IN")}`;

export default function ControlPanelPage() {
  const [userId, setUserId] = useState<string>("");
  const [rows, setRows] = useState<Delegation[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // create form
  const [perTxn, setPerTxn] = useState("1000");
  const [daily, setDaily] = useState("3000");
  const [monthly, setMonthly] = useState("15000");
  const [category, setCategory] = useState("GROCERY");
  const [merchants, setMerchants] = useState("");

  async function refresh(uid: string) {
    setLoading(true);
    try {
      setRows(await listDelegations(uid));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    getAgenticMe()
      .then(({ user_id }) => {
        setUserId(user_id);
        return refresh(user_id);
      })
      .catch((e) => {
        setError((e as Error).message);
        setLoading(false);
      });
  }, []);

  async function onCreate() {
    setBusy("create");
    setError(null);
    try {
      await createDelegation({
        user_id: userId,
        per_txn_paise: Math.round(parseFloat(perTxn) * 100),
        daily_paise: Math.round(parseFloat(daily) * 100),
        monthly_paise: Math.round(parseFloat(monthly) * 100),
        allowed_categories: [category.trim().toUpperCase()],
        allowed_merchants: merchants.trim()
          ? merchants.split(",").map((m) => m.trim()).filter(Boolean)
          : [],
      });
      await refresh(userId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function onAction(id: string, action: "revoke" | "pause" | "resume") {
    setBusy(id + action);
    try {
      await delegationAction(id, action);
      await refresh(userId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function onKill(mode: "pause-payments" | "resume-payments") {
    setBusy(mode);
    try {
      await killSwitch(userId, mode);
      await refresh(userId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 py-6">
      <header className="space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-white shadow-glow">
            <ShieldCheck size={18} />
          </div>
          <h1 className="text-lg font-semibold">Agent Control Panel</h1>
        </div>
        <p className="text-sm text-muted">
          Register spending authority for your agent, set the rules (category, merchants, limits),
          and revoke or pause it any time. This is the user-facing layer over UPI-Circle-style
          delegation.
        </p>
      </header>

      {/* Kill switch */}
      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-surface/60 p-3">
        <Power size={16} className="text-bad" />
        <span className="text-sm font-medium">Emergency kill switch</span>
        <span className="text-xs text-muted">pause / resume all agent payments at once</span>
        <div className="ml-auto flex gap-2">
          <button
            type="button"
            onClick={() => onKill("pause-payments")}
            disabled={!!busy || !userId}
            className="inline-flex items-center gap-1.5 rounded-lg border border-bad/40 bg-bad/10 px-3 py-1.5 text-sm text-bad disabled:opacity-50"
          >
            <Pause size={14} /> Pause all
          </button>
          <button
            type="button"
            onClick={() => onKill("resume-payments")}
            disabled={!!busy || !userId}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-elevated px-3 py-1.5 text-sm disabled:opacity-50"
          >
            <Play size={14} /> Resume all
          </button>
        </div>
      </div>

      {/* Create delegation */}
      <section className="rounded-2xl border border-line bg-surface/60 p-4">
        <h2 className="mb-3 text-sm font-semibold">Grant a new authority</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Field label="Category">
            <input value={category} onChange={(e) => setCategory(e.target.value)} className={inputCls} />
          </Field>
          <Field label="Per-transaction (₹)">
            <input value={perTxn} onChange={(e) => setPerTxn(e.target.value)} inputMode="decimal" className={inputCls} />
          </Field>
          <Field label="Daily cap (₹)">
            <input value={daily} onChange={(e) => setDaily(e.target.value)} inputMode="decimal" className={inputCls} />
          </Field>
          <Field label="Monthly cap (₹)">
            <input value={monthly} onChange={(e) => setMonthly(e.target.value)} inputMode="decimal" className={inputCls} />
          </Field>
          <Field label="Merchants (optional, comma-sep)" wide>
            <input
              value={merchants}
              onChange={(e) => setMerchants(e.target.value)}
              placeholder="empty = any merchant in category"
              className={inputCls}
            />
          </Field>
        </div>
        <button
          type="button"
          onClick={onCreate}
          disabled={!!busy || !userId}
          className="mt-3 inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white shadow-glow disabled:opacity-50"
        >
          {busy === "create" ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
          Create delegation
        </button>
      </section>

      {error && (
        <div className="rounded-xl border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{error}</div>
      )}

      {/* Delegations list */}
      <section className="rounded-2xl border border-line bg-surface/60 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Active authorities</h2>
          <button
            type="button"
            onClick={() => userId && refresh(userId)}
            className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-primary"
          >
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </div>
        ) : rows.length === 0 ? (
          <p className="py-6 text-sm text-muted">
            No delegations yet. Create one above, or run an agentic checkout — the agent creates one
            automatically.
          </p>
        ) : (
          <ul className="space-y-2">
            {rows.map((d) => (
              <li key={d.id} className="rounded-xl border border-line bg-elevated p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-mono text-xs text-muted">{d.id}</span>
                      <StatusBadge status={d.status} />
                    </div>
                    <p className="mt-1 text-sm">
                      {d.allowed_categories.join(", ")} ·{" "}
                      {d.allowed_merchants.length ? d.allowed_merchants.join(", ") : "any merchant"}
                    </p>
                    <p className="mt-0.5 text-xs text-muted">
                      per-txn {rupees(d.limits.per_txn_paise)} · daily {rupees(d.limits.daily_paise)} ·
                      monthly {rupees(d.limits.monthly_paise)}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-1.5">
                    {d.status === "ACTIVE" && (
                      <IconBtn label="Pause" busy={busy === d.id + "pause"} onClick={() => onAction(d.id, "pause")}>
                        <Pause size={14} />
                      </IconBtn>
                    )}
                    {d.status === "PAUSED" && (
                      <IconBtn label="Resume" busy={busy === d.id + "resume"} onClick={() => onAction(d.id, "resume")}>
                        <Play size={14} />
                      </IconBtn>
                    )}
                    {d.status !== "REVOKED" && (
                      <IconBtn label="Revoke" danger busy={busy === d.id + "revoke"} onClick={() => onAction(d.id, "revoke")}>
                        <Ban size={14} />
                      </IconBtn>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-line bg-elevated px-3 py-2 text-sm text-primary outline-none focus-visible:ring-2 focus-visible:ring-accent";

function Field({ label, wide, children }: { label: string; wide?: boolean; children: React.ReactNode }) {
  return (
    <label className={`flex flex-col gap-1 ${wide ? "col-span-2 sm:col-span-3" : ""}`}>
      <span className="text-[11px] font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "ACTIVE"
      ? "bg-good/15 text-good"
      : status === "PAUSED"
        ? "bg-warn/15 text-warn"
        : "bg-bad/15 text-bad";
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${tone}`}>{status}</span>;
}

function IconBtn({
  label,
  danger,
  busy,
  onClick,
  children,
}: {
  label: string;
  danger?: boolean;
  busy?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      aria-label={label}
      title={label}
      className={`grid h-8 w-8 place-items-center rounded-lg border disabled:opacity-50 ${
        danger ? "border-bad/40 bg-bad/10 text-bad" : "border-line bg-surface text-muted hover:text-primary"
      }`}
    >
      {busy ? <Loader2 size={14} className="animate-spin" /> : children}
    </button>
  );
}
