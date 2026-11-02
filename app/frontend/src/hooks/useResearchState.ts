import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

export interface ResearchMemory {
  scope: string;
  values: Map<string, unknown>;
}

export const ResearchContext = createContext<ResearchMemory | null>(null);

/** Retains a control across route remounts; undefined keys opt out of retention. */
export function useResearchState<T>(
  key: string | undefined,
  initialValue: T | (() => T),
): [T, Dispatch<SetStateAction<T>>] {
  const memory = useContext(ResearchContext);
  if (key !== undefined && !memory) {
    throw new Error("Research state requires a ResearchProvider");
  }
  const storageKey = key === undefined ? undefined : `${memory?.scope}\0${key}`;
  const values = memory?.values;
  const [value, setValue] = useState<T>(() => {
    if (storageKey !== undefined && values?.has(storageKey)) {
      return values.get(storageKey) as T;
    }
    return typeof initialValue === "function" ? (initialValue as () => T)() : initialValue;
  });
  const current = useRef(value);
  const update = useCallback<Dispatch<SetStateAction<T>>>(
    (action) => {
      const next =
        typeof action === "function" ? (action as (previous: T) => T)(current.current) : action;
      current.current = next;
      if (storageKey !== undefined) values?.set(storageKey, next);
      setValue(next);
    },
    [storageKey, values],
  );
  return [value, update];
}
