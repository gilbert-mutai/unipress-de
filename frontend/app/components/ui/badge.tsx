import { cn } from "../../lib/utils";

// Verdict → color mapping (semantic; readable in light + dark).
const VERDICT: Record<string, string> = {
  SUPPORTED: "bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300",
  INTERPRETATION: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  RHETORICAL: "bg-line/70 text-muted",
  UNSUPPORTED: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  CONTRADICTED: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
};

// Truncate rather than round, so a confidence never displays higher than it is.
// Rounding put 0.445 on screen as "0.45" next to an UNSUPPORTED verdict, while the
// INTERPRETATION threshold is 0.45 — making a correct verdict look like a bug.
function floor2(value: number): string {
  return (Math.floor(value * 100) / 100).toFixed(2);
}

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
      {confidence != null && <span className="opacity-70">{floor2(confidence)}</span>}
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
