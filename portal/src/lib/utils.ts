import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Status -> label + badge class for voice notes. */
export const STATUS_META: Record<string, { label: string; className: string }> = {
  received: { label: "Received", className: "bg-blue-100 text-blue-800 border-blue-200" },
  accepted: { label: "Accepted", className: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  rejected: { label: "Rejected", className: "bg-rose-100 text-rose-800 border-rose-200" },
  needs_review: { label: "Needs review", className: "bg-amber-100 text-amber-800 border-amber-200" },
};

export function statusBadge(status: string) {
  return STATUS_META[status] ?? { label: status, className: "bg-neutral-100 text-neutral-800 border-neutral-200" };
}

export function formatDate(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
