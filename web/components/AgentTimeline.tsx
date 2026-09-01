import type { Step } from "@/lib/api";
import { isTerminalState, stateLabel } from "@/lib/labels";

export function AgentTimeline({ steps, running = false }: { steps: Step[]; running?: boolean }) {
  if (steps.length === 0) {
    return (
      <div className="py-6 text-center">
        <p className="text-sm font-medium text-white/90">Your agent&apos;s activity will appear here.</p>
        <p className="mt-1 text-xs text-muted">
          Submit an instruction to watch the agent work through your order.
        </p>
      </div>
    );
  }

  const lastIndex = steps.length - 1;

  return (
    <ol
      className="timeline m-0 max-h-[520px] list-none space-y-0 overflow-auto p-0"
      role="list"
      aria-live="polite"
      aria-label="Agent activity"
    >
      {steps.map((s, i) => {
        const isLast = i === lastIndex;
        // Still-running last step is "active"; error steps are marked failed.
        const failed = s.state === "ERROR" || s.state === "FAILED";
        const active = isLast && running && !failed && !isTerminalState(s.state);
        return (
          <li key={s.index} className="flex gap-3 border-b border-dashed border-line py-2.5 last:border-0">
            <span className="mt-0.5 shrink-0" aria-hidden="true">
              {failed ? (
                <Dot className="text-bad">✕</Dot>
              ) : active ? (
                <span className="spinner-sm inline-block" />
              ) : (
                <Dot className="text-good">✓</Dot>
              )}
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-medium text-white/90">{stateLabel(s.state)}</span>
              {s.message && <span className="mt-0.5 block text-xs text-muted">{s.message}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function Dot({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex h-4 w-4 items-center justify-center text-[11px] font-bold ${className ?? ""}`}>
      {children}
    </span>
  );
}
