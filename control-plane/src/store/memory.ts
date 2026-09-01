/**
 * In-memory stores (Phase 0 sandbox).
 *
 * Production binding (freeze D4) is Postgres 16 + Prisma with unique
 * constraints that make double-spend representable-but-not-committable, plus
 * Redis 7 for the nonce registry and revocation cache. These in-memory
 * equivalents preserve the same semantics so the control-plane logic and its
 * red-team suite run with zero infrastructure.
 */

import type { Paise, LedgerView } from "../domain/types.ts";

interface SpendRecord {
  delegation_id: string;
  amount_paise: Paise;
  at: Date;
}

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_MS = 7 * DAY_MS;
const MONTH_MS = 30 * DAY_MS;

/**
 * Records settled spend and produces the velocity view CAN_PAY() reads. Uses
 * rolling windows; sums are computed at decision time from committed records
 * only (so an in-flight, not-yet-settled intent never inflates the budget).
 */
export class SpendLedger {
  #records: SpendRecord[] = [];

  record(delegationId: string, amountPaise: Paise, at: Date): void {
    this.#records.push({ delegation_id: delegationId, amount_paise: amountPaise, at });
  }

  view(delegationId: string, now: Date): LedgerView {
    const t = now.getTime();
    let daily = 0;
    let weekly = 0;
    let monthly = 0;
    for (const r of this.#records) {
      if (r.delegation_id !== delegationId) continue;
      const age = t - r.at.getTime();
      if (age < 0) continue;
      if (age <= DAY_MS) daily += r.amount_paise;
      if (age <= WEEK_MS) weekly += r.amount_paise;
      if (age <= MONTH_MS) monthly += r.amount_paise;
    }
    return { spent_daily_paise: daily, spent_weekly_paise: weekly, spent_monthly_paise: monthly };
  }

  /** Average settled spend for a delegation within a rolling window (0 if none). */
  recentAverage(delegationId: string, now: Date, windowMs = MONTH_MS): Paise {
    const t = now.getTime();
    const amounts = this.#records
      .filter((r) => r.delegation_id === delegationId && t - r.at.getTime() <= windowMs && t - r.at.getTime() >= 0)
      .map((r) => r.amount_paise);
    if (amounts.length === 0) return 0;
    return Math.round(amounts.reduce((a, b) => a + b, 0) / amounts.length);
  }
}
