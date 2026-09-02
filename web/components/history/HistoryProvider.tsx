"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { DecideResponse } from "@/lib/api";

export interface HistoryEntry {
  id: string;
  query: string;
  result: DecideResponse;
  at: number;
}

interface HistoryContextValue {
  history: HistoryEntry[];
  selectedId: string | null;
  selected: HistoryEntry | null;
  add: (query: string, result: DecideResponse) => void;
  select: (id: string) => void;
  remove: (id: string) => void;
  newChat: () => void;
  clearAll: () => void;
}

const HistoryContext = createContext<HistoryContextValue | null>(null);

const STORAGE_KEY = "syncore-history";
const MAX_ENTRIES = 40;

export function HistoryProvider({ children }: { children: React.ReactNode }) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Hydrate from localStorage after mount.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setHistory(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  const persist = useCallback((next: HistoryEntry[]) => {
    setHistory(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }, []);

  const add = useCallback(
    (query: string, result: DecideResponse) => {
      const entry: HistoryEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        query,
        result,
        at: Date.now(),
      };
      persist([entry, ...history].slice(0, MAX_ENTRIES));
      setSelectedId(entry.id);
    },
    [history, persist],
  );

  const select = useCallback((id: string) => setSelectedId(id), []);
  const newChat = useCallback(() => setSelectedId(null), []);

  const remove = useCallback(
    (id: string) => {
      persist(history.filter((h) => h.id !== id));
      setSelectedId((cur) => (cur === id ? null : cur));
    },
    [history, persist],
  );

  const clearAll = useCallback(() => {
    persist([]);
    setSelectedId(null);
  }, [persist]);

  const selected = useMemo(
    () => history.find((h) => h.id === selectedId) ?? null,
    [history, selectedId],
  );

  const value: HistoryContextValue = {
    history,
    selectedId,
    selected,
    add,
    select,
    remove,
    newChat,
    clearAll,
  };

  return <HistoryContext.Provider value={value}>{children}</HistoryContext.Provider>;
}

export function useHistory(): HistoryContextValue {
  const ctx = useContext(HistoryContext);
  if (!ctx) throw new Error("useHistory must be used within HistoryProvider");
  return ctx;
}
