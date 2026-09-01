/**
 * Server-authoritative clock (Blueprint check 3: "server clock is authoritative").
 * Injectable so tests can pin time and exercise expiry / velocity windows.
 */

export type Clock = () => Date;

export const systemClock: Clock = () => new Date();

export function iso(clock: Clock): string {
  return clock().toISOString();
}

/** A controllable clock for tests. */
export class FakeClock {
  #now: Date;
  constructor(start: string | Date = "2026-09-01T00:00:00.000Z") {
    this.#now = new Date(start);
  }
  now: Clock = () => new Date(this.#now);
  advanceMs(ms: number): void {
    this.#now = new Date(this.#now.getTime() + ms);
  }
  set(when: string | Date): void {
    this.#now = new Date(when);
  }
}
