import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function toInitCap(s: string | null | undefined): string {
  if (!s) return "";
  return s.toLowerCase().replace(/(?:^|\s|[-/])\S/g, (c) => c.toUpperCase());
}
