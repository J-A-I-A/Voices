/**
 * Jamaica-only WhatsApp number normalization (mirrors the backend).
 * Accepts flexible input; normalizes to E.164 "+1876XXXXXXX" or "+1658XXXXXXX".
 */
const JAMAICA_AREA_CODES = new Set(["876", "658"]);

export class InvalidJamaicanNumberError extends Error {}

export function normalizeJamaican(raw: string): string {
  const digits = (raw ?? "").replace(/\D+/g, "");
  if (!digits) throw new InvalidJamaicanNumberError("Phone number is required.");
  let d = digits;
  if (d.length === 11 && d.startsWith("1")) d = d.slice(1);
  if (d.length === 10) {
    const area = d.slice(0, 3);
    const rest = d.slice(3);
    if (JAMAICA_AREA_CODES.has(area) && rest.length === 7 && !/^[01]/.test(d)) {
      return "+1" + d;
    }
    throw new InvalidJamaicanNumberError(
      "Only Jamaican WhatsApp numbers (876 or 658) can register at this time."
    );
  }
  if (d.length === 11 && d.startsWith("1")) {
    const area = d.slice(1, 4);
    const rest = d.slice(4);
    if (JAMAICA_AREA_CODES.has(area) && rest.length === 7) {
      return "+" + d;
    }
  }
  throw new InvalidJamaicanNumberError(
    "Only Jamaican WhatsApp numbers (876 or 658) can register at this time."
  );
}

export function isJamaicanE164(v?: string | null): boolean {
  return !!v && /^\+1(?:876|658)\d{7}$/.test(v);
}

export function ageFromDob(dob: string | Date, today = new Date()): number {
  const d = typeof dob === "string" ? new Date(dob) : dob;
  let age = today.getFullYear() - d.getFullYear();
  const m = today.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < d.getDate())) age--;
  return age;
}

export function isAtLeast18(dob: string | Date): boolean {
  return ageFromDob(dob) >= 18;
}
