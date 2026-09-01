/**
 * Risk Engine v0 (Blueprint 5.2, W5).
 *
 * Machine-initiated spend has a different risk topology from human spend. v0
 * ships THREE deterministic signals with honest thresholds (not a neural
 * mythology): prompt-injection content shape, velocity spikes, and amount
 * anomaly versus recent history. Output is LOW / MEDIUM / HIGH with fixed
 * outcomes that feed CAN_PAY() check 11 (HIGH denies, MEDIUM challenges).
 */

import { canonicalJson } from "../crypto/canonical.ts";
import type { Delegation, PaymentIntentProposal, RiskVerdict } from "../domain/types.ts";

export interface RiskContext {
  recent_intents_60s: number;
  avg_recent_spend_paise: number; // 0 when there is no history
  delegation_age_seconds: number;
}

// Content-shape patterns suggestive of injected instructions inside untrusted
// commerce text that leaked into a proposal. Authority never depends on this —
// it is an additional signal, not the control (Blueprint R4).
const INJECTION_PATTERNS: RegExp[] = [
  /ignore\s+(all\s+)?previous\s+instructions/i,
  /disregard\s+(the\s+)?(system|prior)/i,
  /override\s+(policy|limit|budget)/i,
  /\b(transfer|wire|remit)\b.*\b(to|into)\b/i,
  /\bgift\s*card\b/i,
  /\b(share|send|read)\b.*\b(otp|pin|cvv|password)\b/i,
  /<script|drop\s+table|;--/i,
];

const VELOCITY_SPIKE = 5; // >= 5 intents in 60s looks like a retry storm
const AMOUNT_SPIKE_RATIO = 10; // >= 10x recent average is anomalous

export class RiskEngine {
  score(proposal: PaymentIntentProposal, _delegation: Delegation, ctx: RiskContext): RiskVerdict {
    const blob = canonicalJson(proposal);
    const injection = INJECTION_PATTERNS.some((re) => re.test(blob));
    const velocitySpike = ctx.recent_intents_60s >= VELOCITY_SPIKE;
    const amountSpike =
      ctx.avg_recent_spend_paise > 0 &&
      proposal.amount_paise >= ctx.avg_recent_spend_paise * AMOUNT_SPIKE_RATIO;

    const signals: RiskVerdict["signals"] = {
      injection_shape: injection,
      recent_intents_60s: ctx.recent_intents_60s,
      velocity_spike: velocitySpike,
      amount_spike: amountSpike,
      delegation_age_seconds: Math.round(ctx.delegation_age_seconds),
    };

    if (injection) {
      return { level: "HIGH", signals, reason: "content-shape suggests injected instructions" };
    }
    if (velocitySpike || amountSpike) {
      return {
        level: "MEDIUM",
        signals,
        reason: velocitySpike ? "velocity spike (possible retry storm)" : "amount anomaly vs history",
      };
    }
    return { level: "LOW", signals, reason: "no elevated agentic-risk signals" };
  }
}
