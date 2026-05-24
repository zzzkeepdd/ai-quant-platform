import clsx from "clsx";
import React from "react";

export function Card({ className, children }: React.PropsWithChildren<{ className?: string }>) {
  return <section className={clsx("glass rounded-xl p-5 transition duration-200 hover:border-[var(--app-line)]", className)}>{children}</section>;
}

export function Button({ className, variant = "primary", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "warn" }) {
  return (
    <button
      className={clsx(
        "inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-medium transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-[var(--app-button-bg)] text-[var(--app-button-text)] hover:bg-[var(--app-button-hover)]",
        variant === "ghost" && "border border-[var(--app-line)] bg-[var(--app-soft)] text-[var(--app-text)] hover:bg-[var(--app-hover)]",
        variant === "danger" && "bg-red-500/90 text-white hover:bg-red-500",
        variant === "warn" && "bg-yellow-400 text-black hover:bg-yellow-300",
        className
      )}
      {...props}
    />
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx("surface-field h-10 w-full rounded-xl border px-3 text-sm outline-none transition placeholder:text-app-muted focus:border-[var(--app-text)]/30", props.className)} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={clsx("surface-field h-10 w-full rounded-xl border px-3 text-sm outline-none focus:border-[var(--app-text)]/30", props.className)} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={clsx("surface-field min-h-28 w-full rounded-xl border p-3 text-sm outline-none focus:border-[var(--app-text)]/30", props.className)} />;
}

export function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "up" | "down" | "warn" }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-app-muted">{label}</div>
      <div className={clsx("mt-2 text-3xl font-semibold tracking-normal", tone === "up" && "text-success", tone === "down" && "text-danger", tone === "warn" && "text-warning")}>{value}</div>
    </Card>
  );
}

export function Badge({ children, tone = "neutral" }: React.PropsWithChildren<{ tone?: "neutral" | "up" | "down" | "warn" }>) {
  return <span className={clsx("rounded-full border px-2.5 py-1 text-xs", tone === "neutral" && "border-[var(--app-line)] bg-[var(--app-soft)] text-[var(--app-muted)]", tone === "up" && "border-green-500/25 bg-green-500/10 text-success", tone === "down" && "border-red-500/25 bg-red-500/10 text-danger", tone === "warn" && "border-yellow-500/25 bg-yellow-500/10 text-warning")}>{children}</span>;
}
