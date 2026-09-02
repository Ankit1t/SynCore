"use client";

import { useEffect, useState } from "react";
import { getFeatureFlags } from "@/lib/api";

export default function PreferencesPage() {
  const [flags, setFlags] = useState<Record<string, unknown>>({});

  useEffect(() => {
    getFeatureFlags().then(setFlags).catch(() => setFlags({}));
  }, []);

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6 lg:px-8">
      <h2 className="mb-4 text-lg font-semibold">Preferences</h2>
      <p className="mb-4 text-sm text-muted">
        Your shopping preferences — preferred brands, minimum rating, substitution rules and
        default budget — guide how your agent chooses products. This environment&apos;s current
        agent settings are shown below.
      </p>
      <div className="card p-4">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
          Agent settings
        </h3>
        <table className="w-full text-sm">
          <tbody>
            {Object.entries(flags).map(([k, v]) => (
              <tr key={k}>
                <td className="border-b border-line py-2 text-muted">{k}</td>
                <td className="border-b border-line py-2 font-mono">{String(v)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
