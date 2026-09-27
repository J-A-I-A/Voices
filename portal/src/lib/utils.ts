import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Status -> label + badge class for voice notes. */
export const STATUS_META: Record<string, { label: string; className: string }> = {
  received: { label: "Received", className: "bg-sky-50 text-sky-700 border-sky-200" },
  accepted: { label: "Accepted", className: "bg-[color:var(--jaia-green-soft)] text-[#06502a] border-[color:var(--jaia-green)]/30" },
  rejected: { label: "Rejected", className: "bg-rose-50 text-rose-700 border-rose-200" },
  needs_review: { label: "Needs review", className: "bg-[color:var(--jaia-gold-soft)] text-[#8a5a00] border-[color:var(--jaia-gold)]/50" },
};

export function statusBadge(status: string) {
  return STATUS_META[status] ?? { label: status, className: "bg-[color:var(--paper-warm)] text-[color:var(--ink-soft)] border-[color:var(--line)]" };
}

export function formatDate(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
