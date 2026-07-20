import { DocumentRead } from "../lib/api";
import { cn } from "../lib/utils";

const STAGES = ["Parse", "Chunk", "Claims", "Embed"];

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-xl border border-line bg-paper px-4 py-3 text-center">
      <div className="font-serif text-2xl font-semibold tabular-nums">{value ?? "—"}</div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}

export function PipelineProgress({ doc }: { doc: DocumentRead }) {
  const done = doc.status === "done";
  const failed = doc.status === "failed";

  if (done) {
    return (
      <div className="mt-4 grid grid-cols-3 gap-3 animate-fade-up">
        <Stat label="Pages" value={doc.page_count} />
        <Stat label="Chunks" value={doc.chunk_count} />
        <Stat label="Claims" value={doc.claim_count} />
      </div>
    );
  }

  if (failed) {
    return (
      <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
        Ingestion failed{doc.error ? `: ${doc.error}` : ""}.
      </p>
    );
  }

  return (
    <div className="mt-4">
      <div className="flex items-center gap-2 text-sm text-muted">
        {STAGES.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <span className={cn("h-2 w-2 rounded-full bg-brand", i === 0 && "animate-pulse")} />
            <span>{s}</span>
            {i < STAGES.length - 1 && <span className="text-line">→</span>}
          </div>
        ))}
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-line/60">
        <div className="skeleton h-full w-1/2 rounded-full bg-brand/40" />
      </div>
    </div>
  );
}
