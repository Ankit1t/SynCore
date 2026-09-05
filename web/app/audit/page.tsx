"use client";

import { useEffect, useState } from "react";
import {
  ScrollText,
  ShieldCheck,
  ShieldAlert,
  Check,
  X,
  Loader2,
  ChevronRight,
  FileSignature,
} from "lucide-react";
import {
  getAuditDetail,
  listAudit,
  type AuditDetail,
  type AuditRow,
  type MandateCheck,
} from "@/lib/api";

const rupees = (paise: number | null) => (paise == null ? "—" : `₹${(paise / 100).toFixed(2)}`);
const shortHash = (h?: string) => (h ? `${h.replace("sha256:", "").slice(0, 8)}…` : "—");

export default function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<AuditDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAudit()
      .then(setRows)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  async function open(intentId: string) {
    setSelected(intentId);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await getAuditDetail(intentId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 py-6">
      <header className="space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-white shadow-glow">
            <ScrollText size={18} />
          </div>
          <h1 className="text-lg font-semibold">Audit &amp; Dispute Trail</h1>
        </div>
        <p className="text-sm text-muted">
          Every gate decision and payment leaves a non-repudiable record: the signed intent → cart →
          payment mandate chain. In a dispute, this proves exactly what the user authorized.
        </p>
      </header>

      {error && (
        <div className="rounded-xl border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{error}</div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-6 text-sm text-muted">
          <Loader2 size={16} className="animate-spin" /> Loading trail…
        </div>
      ) : rows.length === 0 ? (
        <p className="py-6 text-sm text-muted">
          No transactions yet. Run an agentic checkout on the AgentGuard page, then come back here.
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.intent_id}>
              <button
                type="button"
                onClick={() => open(r.intent_id)}
                className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors ${
                  selected === r.intent_id ? "border-accent/50 bg-elevated" : "border-line bg-surface/60 hover:bg-elevated/60"
                }`}
              >
                <OutcomeDot outcome={r.decision_outcome} stage={r.stage} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-primary">{r.text}</p>
                  <p className="text-[11px] text-muted">
                    {new Date(r.created_at).toLocaleString()} · {r.merchant_id ?? "—"} · {rupees(r.amount_paise)}
                  </p>
                </div>
                <span className="shrink-0 text-xs font-medium">{stageLabel(r)}</span>
                <ChevronRight size={15} className="shrink-0 text-muted" />
              </button>

              {selected === r.intent_id && (
                <div className="mt-2 rounded-xl border border-line bg-surface/60 p-4">
                  {detailLoading || !detail ? (
                    <div className="flex items-center gap-2 text-sm text-muted">
                      <Loader2 size={15} className="animate-spin" /> Verifying signatures…
                    </div>
                  ) : (
                    <DetailView detail={detail} />
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DetailView({ detail }: { detail: AuditDetail }) {
  const rep = detail.verify_report;
  const chain = detail.ap2_mandates;
  return (
    <div className="space-y-4">
      {/* chain-level verdict */}
      <div
        className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold ${
          rep.chain_valid ? "border-good/40 bg-good/10 text-good" : "border-bad/40 bg-bad/10 text-bad"
        }`}
      >
        {rep.chain_valid ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
        {rep.chain_valid ? "Evidence chain verified — signatures valid" : "Evidence chain INVALID — tampered or unsigned"}
      </div>

      {/* mandates */}
      <div className="space-y-2">
        <MandateRow
          title="IntentMandate"
          subtitle="signed by user"
          digest={chain?.intent_mandate.content_digest as string}
          check={rep.intent_mandate}
        />
        <MandateRow
          title="CartMandate"
          subtitle={`cart ${shortHash(chain?.cart_mandate.cart_hash)}`}
          digest={chain?.cart_mandate.content_digest as string}
          check={rep.cart_mandate}
        />
        {chain?.payment_mandate && rep.payment_mandate && (
          <MandateRow
            title="PaymentMandate"
            subtitle={`${(chain.payment_mandate as { policy_outcome?: string }).policy_outcome ?? ""}`}
            digest={chain.payment_mandate.content_digest as string}
            check={rep.payment_mandate}
          />
        )}
      </div>

      {/* CAN_PAY decision */}
      {detail.decision && (
        <div>
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-muted">
            <FileSignature size={13} className="text-accent" /> CAN_PAY() verdict:{" "}
            <span className="text-primary">{detail.decision.outcome}</span>
            {detail.decision.rule_fired && <span className="text-bad">· {detail.decision.rule_fired}</span>}
          </p>
        </div>
      )}

      {detail.receipt && (
        <details className="rounded-lg border border-line bg-elevated p-2">
          <summary className="cursor-pointer text-xs font-medium text-muted">Receipt JSON</summary>
          <pre className="mt-2 max-h-48 overflow-auto text-[11px] text-muted">
            {JSON.stringify(detail.receipt, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

function MandateRow({
  title,
  subtitle,
  digest,
  check,
}: {
  title: string;
  subtitle: string;
  digest?: string;
  check?: MandateCheck;
}) {
  return (
    <div className="rounded-xl border border-line bg-elevated p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{title}</span>
        <span className="text-[11px] text-muted">{subtitle}</span>
      </div>
      <p className="mt-0.5 truncate font-mono text-[11px] text-muted" title={digest}>
        {digest ?? "—"}
      </p>
      {check && (
        <div className="mt-1.5 flex flex-wrap gap-2 text-[11px]">
          <Flag label="digest" ok={check.digest_ok} />
          <Flag label="chain link" ok={check.link_ok} />
          <Flag label="signature" ok={check.signature_ok} />
          {check.signer_id && <span className="text-muted">signer: {check.signer_id}</span>}
        </div>
      )}
    </div>
  );
}

function Flag({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 ${ok ? "text-good" : "text-bad"}`}>
      {ok ? <Check size={12} /> : <X size={12} />} {label}
    </span>
  );
}

function OutcomeDot({ outcome, stage }: { outcome: string | null; stage: string }) {
  const good = outcome === "ALLOW" && stage !== "BLOCKED";
  const tone = stage === "BLOCKED" || outcome === "DENY" ? "bg-bad" : good ? "bg-good" : "bg-warn";
  return <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${tone}`} />;
}

function stageLabel(r: AuditRow): string {
  if (r.stage === "BLOCKED") return "BLOCKED";
  if (r.stage === "SETTLED") return "SETTLED";
  if (r.stage === "CHECKOUT_REQUIRED") return "AWAITING PAY";
  return r.decision_outcome ?? r.stage;
}
