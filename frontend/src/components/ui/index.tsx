"use client";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import toast from "react-hot-toast";

// ── Spinner ───────────────────────────────────────────────────
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("animate-spin", className)} />;
}

// ── Badge ─────────────────────────────────────────────────────
export function Badge({
  children, className,
}: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("badge", className)}>{children}</span>
  );
}

// ── Card ──────────────────────────────────────────────────────
export function Card({
  children, className, onClick,
}: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return (
    <div className={cn("card p-5", className)} onClick={onClick}>
      {children}
    </div>
  );
}

// ── Progress Bar ──────────────────────────────────────────────
export function ProgressBar({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn("w-full bg-gray-100 rounded-full h-2", className)}>
      <div
        className="h-2 rounded-full bg-indigo-600 transition-all duration-500"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}

// ── Score Circle ──────────────────────────────────────────────
export function ScoreCircle({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";
  const sizes = { sm: 48, md: 72, lg: 96 };
  const px = sizes[size];
  const r = px / 2 - 5;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const fs = size === "sm" ? "text-sm" : size === "lg" ? "text-2xl" : "text-lg";

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: px, height: px }}>
      <svg width={px} height={px} viewBox={`0 0 ${px} ${px}`}>
        <circle cx={px/2} cy={px/2} r={r} fill="none" stroke="#e5e7eb" strokeWidth="4" />
        <circle cx={px/2} cy={px/2} r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={circ} strokeDashoffset={offset}
          transform={`rotate(-90 ${px/2} ${px/2})`}
          strokeLinecap="round" style={{ transition: "stroke-dashoffset 0.6s" }} />
      </svg>
      <span className={cn("absolute font-bold", fs)} style={{ color }}>{score.toFixed(0)}</span>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────
export function EmptyState({
  icon, title, description, action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && <div className="text-gray-300 mb-3">{icon}</div>}
      <p className="text-gray-900 font-medium">{title}</p>
      {description && <p className="text-gray-500 text-sm mt-1">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ── Alert ─────────────────────────────────────────────────────
export function Alert({
  type = "info", children,
}: { type?: "info" | "success" | "warning" | "error"; children: React.ReactNode }) {
  const styles = {
    info:    "bg-blue-50 border-blue-200 text-blue-800",
    success: "bg-green-50 border-green-200 text-green-800",
    warning: "bg-yellow-50 border-yellow-200 text-yellow-800",
    error:   "bg-red-50 border-red-200 text-red-800",
  };
  return (
    <div className={cn("rounded-lg border p-3 text-sm", styles[type])}>
      {children}
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse bg-gray-100 rounded", className)} />;
}

// ── Textarea ──────────────────────────────────────────────────
export function Textarea({
  className, rows = 4, ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { className?: string }) {
  return (
    <textarea
      rows={rows}
      className={cn("input resize-none", className)}
      {...props}
    />
  );
}

// ── CopyButton ────────────────────────────────────────────────
export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const copy = () => {
    navigator.clipboard.writeText(text);
    toast.success("Copied!");
  };
  return (
    <button onClick={copy} className="btn-secondary text-xs py-1 px-3">
      {label}
    </button>
  );
}
