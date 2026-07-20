import { DocumentRead } from "../lib/api";

const STAGE_LABEL: Record<string, string> = {
  queued: "Queued",
  parse: "Parsing the PDF",
  chunk: "Splitting into passages",
  extract: "Extracting claims",
  embed: "Building the search index",
  done: "Done",
};

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-xl border border-line bg-paper px-4 py-3 text-center">
      <div className="font-serif text-2xl font-semibold tabular-nums">{value ?? "—"}</div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}

export function PipelineProgress({ doc }: { doc: DocumentRead }) {
  if (doc.status === "done") {
    return (
      <div className="mt-4 grid grid-cols-3 gap-3 animate-fade-up">
        <Stat label="Pages" value={doc.page_count} />
        <Stat label="Chunks" value={doc.chunk_count} />
        <Stat label="Claims" value={doc.claim_count} />
      </div>
    );
  }

  if (doc.status === "failed") {
    return (
      <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
        Ingestion failed{doc.error ? `: ${doc.error}` : ""}.
      </p>
    );
  }

  const pct = doc.progress ?? 5;
  const label = STAGE_LABEL[doc.stage ?? "queued"] ?? "Working";

  return (
    <div className="mt-4">
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 text-ink">
          <span className="h-2 w-2 animate-pulse rounded-full bg-brand" />
          {label}…
        </span>
        <span className="font-serif font-semibold tabular-nums text-muted">{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-line/60">
        <div
          className="h-full rounded-full bg-brand transition-[width] duration-700 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
