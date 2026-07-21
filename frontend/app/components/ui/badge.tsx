import { cn } from "../../lib/utils";

// Verdict → color mapping (semantic; readable in light + dark).
const VERDICT: Record<string, string> = {
  SUPPORTED: "bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300",
  INTERPRETATION: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  RHETORICAL: "bg-line/70 text-muted",
  UNSUPPORTED: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  CONTRADICTED: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
};

export function VerdictBadge({
  verdict,
  confidence,
  className,
}: {
  verdict: string;
  confidence?: number | null;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        VERDICT[verdict] ?? "bg-line/70 text-muted",
        className,
      )}
    >
      {verdict}
      {confidence != null && <span className="opacity-70">{confidence.toFixed(2)}</span>}
    </span>
  );
}

export function Chip({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-line bg-paper px-2 py-0.5 text-[11px] text-muted",
        className,
      )}
      {...props}
    />
  );
}
