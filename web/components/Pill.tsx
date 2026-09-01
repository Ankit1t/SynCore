const STATE_TONE: Record<string, string> = {
  COMPLETED: "bg-good/15 text-good",
  CONFIRMED: "bg-good/15 text-good",
  USER_REVIEW_REQUIRED: "bg-warn/15 text-warn",
  PAYMENT_AUTH_REQUIRED: "bg-warn/15 text-warn",
  FAILED: "bg-bad/15 text-bad",
  CANCELLED: "bg-bad/15 text-bad",
  ERROR: "bg-bad/15 text-bad",
};

export function Pill({ label, tone }: { label: string; tone?: string }) {
  const cls = tone || STATE_TONE[label] || "bg-accent/15 text-accent";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${cls}`}>
      {label}
    </span>
  );
}
