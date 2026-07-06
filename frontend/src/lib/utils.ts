import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(date: string | Date) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(date));
}

export function ago(date: string | Date) {
  const s = (Date.now() - new Date(date).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
  return fmt(date);
}

// While the Google OAuth app is in Testing mode, Google expires every
// Gmail connection after exactly 7 days no matter how it's used. Warn at
// 6.5 days so someone gets a heads up and a working reconnect button
// before their next send just fails.
export function gmailExpiry(connectedAt?: string | null) {
  if (!connectedAt) return { daysLeft: null, warn: false, expired: false };
  const elapsedDays = (Date.now() - new Date(connectedAt).getTime()) / 86400000;
  const daysLeft = Math.max(0, 7 - elapsedDays);
  return { daysLeft, warn: daysLeft <= 0.5, expired: daysLeft <= 0 };
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$", EUR: "€", GBP: "£", INR: "₹", CAD: "$", AUD: "$",
};

export function fmtSalary(min?: number | null, max?: number | null, currency = "USD") {
  if (!min && !max) return null;
  const symbol = CURRENCY_SYMBOLS[currency] || `${currency} `;
  const f = (n: number) => n >= 1000 ? `${symbol}${(n / 1000).toFixed(0)}k` : `${symbol}${n}`;
  if (min && max) return `${f(min)} – ${f(max)}`;
  if (min) return `${f(min)}+`;
  return `up to ${f(max!)}`;
}

export const STATUS_LABEL: Record<string, string> = {
  generating: "Generating", ready: "Ready", approved: "Approved",
  submitted: "Submitted", screening: "Screening", interviewing: "Interviewing",
  offered: "Offered", rejected: "Rejected", withdrew: "Withdrew", failed: "Failed",
};

export const STATUS_COLOR: Record<string, string> = {
  generating: "bg-blue-50 text-blue-700",
  ready:      "bg-indigo-50 text-indigo-700",
  approved:   "bg-purple-50 text-purple-700",
  submitted:  "bg-green-50 text-green-700",
  screening:  "bg-yellow-50 text-yellow-700",
  interviewing:"bg-cyan-50 text-cyan-700",
  offered:    "bg-emerald-50 text-emerald-700",
  rejected:   "bg-red-50 text-red-700",
  withdrew:   "bg-gray-100 text-gray-600",
  failed:     "bg-red-50 text-red-600",
};

export function fitColor(score: number) {
  if (score >= 80) return "text-emerald-600";
  if (score >= 60) return "text-yellow-600";
  return "text-red-500";
}

export function fitBg(score: number) {
  if (score >= 80) return "bg-emerald-50 border-emerald-200 text-emerald-700";
  if (score >= 60) return "bg-yellow-50 border-yellow-200 text-yellow-700";
  return "bg-red-50 border-red-200 text-red-700";
}
