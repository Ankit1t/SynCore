"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  Plus,
  ShoppingBag,
  Package,
  SlidersHorizontal,
  MessageSquare,
  Trash2,
  Sparkles,
} from "lucide-react";
import { useHistory } from "@/components/history/HistoryProvider";

const NAV = [
  { href: "/", label: "Shop", icon: ShoppingBag },
  { href: "/orders", label: "Orders", icon: Package },
  { href: "/preferences", label: "Preferences", icon: SlidersHorizontal },
];

export function Sidebar() {
  const pathname = usePathname();
  const { history, selectedId, select, remove, newChat, clearAll } = useHistory();
  const onShop = pathname === "/";

  return (
    <aside className="flex h-full w-[260px] shrink-0 flex-col border-r border-line bg-surface/60 backdrop-blur-xl">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-white shadow-glow">
          <Sparkles size={18} />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold">SynCore</p>
          <p className="text-[11px] text-muted">AI Shopping Agent</p>
        </div>
      </div>

      {/* New chat */}
      <div className="px-3">
        <motion.button
          type="button"
          onClick={newChat}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          className="flex w-full items-center gap-2 rounded-xl border border-line bg-elevated px-3 py-2.5 text-sm font-medium text-primary transition-colors hover:border-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Plus size={16} className="text-accent" />
          New chat
        </motion.button>
      </div>

      {/* Nav */}
      <nav className="mt-4 space-y-1 px-3" aria-label="Primary">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`group flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                active
                  ? "bg-elevated font-medium text-primary"
                  : "text-muted hover:bg-elevated/60 hover:text-primary"
              }`}
            >
              <Icon
                size={17}
                className={active ? "text-accent" : "text-muted group-hover:text-primary"}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* History */}
      <div className="mt-5 flex min-h-0 flex-1 flex-col px-3">
        <div className="flex items-center justify-between px-1 pb-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
            Recent
          </span>
          {history.length > 0 && (
            <button
              type="button"
              onClick={clearAll}
              className="rounded text-[11px] text-muted transition-colors hover:text-bad focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Clear
            </button>
          )}
        </div>

        <div className="scroll-thin min-h-0 flex-1 space-y-1 overflow-y-auto pb-3">
          {history.length === 0 ? (
            <p className="px-1 pt-2 text-xs leading-relaxed text-muted">
              Your recent requests will show up here.
            </p>
          ) : (
            <AnimatePresence initial={false}>
              {history.map((h) => {
                const active = onShop && h.id === selectedId;
                return (
                  <motion.div
                    key={h.id}
                    layout
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -8 }}
                    className={`group flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors ${
                      active ? "bg-elevated text-primary" : "text-muted hover:bg-elevated/60"
                    }`}
                  >
                    <MessageSquare size={14} className="shrink-0 text-muted" />
                    <button
                      type="button"
                      onClick={() => select(h.id)}
                      className="min-w-0 flex-1 truncate text-left focus-visible:outline-none"
                      title={h.query}
                    >
                      {h.query}
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(h.id)}
                      aria-label="Delete this request"
                      className="shrink-0 rounded p-1 text-muted opacity-0 transition-opacity hover:text-bad focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent group-hover:opacity-100"
                    >
                      <Trash2 size={13} />
                    </button>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          )}
        </div>
      </div>
    </aside>
  );
}
