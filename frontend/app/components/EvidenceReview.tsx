"use client";

import { useMemo, useState } from "react";
import {
  ClaimRead,
  OutputDetail,
  renderUrl,
  SentenceRead,
  Verdict,
} from "../lib/api";

const VERDICT_STYLE: Record<Verdict, string> = {
  SUPPORTED: "bg-green-100 text-green-800",
  INTERPRETATION: "bg-amber-100 text-amber-800",
  RHETORICAL: "bg-neutral-100 text-neutral-500",
  UNSUPPORTED: "bg-red-100 text-red-800",
  CONTRADICTED: "bg-red-100 text-red-800",
};

function Badge({ s }: { s: SentenceRead }) {
  if (!s.verdict) return null;
  const conf = s.confidence != null ? ` ${s.confidence.toFixed(2)}` : "";
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${VERDICT_STYLE[s.verdict]}`}>
      {s.verdict}
      {conf}
    </span>
  );
}

export default function EvidenceReview({
  output,
  claimsByKey,
}: {
  output: OutputDetail;
  claimsByKey: Record<string, ClaimRead>;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const [accepted, setAccepted] = useState<Set<number>>(new Set());
  const [flagged, setFlagged] = useState<Set<number>>(new Set());

  const toggle = (set: Set<number>, i: number) => {
    const next = new Set(set);
    next.has(i) ? next.delete(i) : next.add(i);
    return next;
  };

  const selectedClaims = useMemo(() => {
    if (selected == null) return [];
    const s = output.sentences.find((x) => x.order_index === selected);
    return (s?.claim_ids ?? []).map((k) => claimsByKey[k]).filter(Boolean);
  }, [selected, output, claimsByKey]);

  return (
    <div>
      {output.coverage?.warnings?.length ? (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          ⚠ {output.coverage.warnings.join(" · ")}
        </div>
      ) : null}

      <div className="mb-4 flex items-center gap-3">
        <a
          href={renderUrl(output.id, "html")}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700"
        >
          Open HTML
        </a>
        <a
          href={renderUrl(output.id, "pdf")}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-100"
        >
          Download PDF
        </a>
        <span className="text-sm text-neutral-500">
          {accepted.size} accepted · {flagged.size} flagged
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Left: generated output */}
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {output.output_type} · {output.language.toUpperCase()}
          </h3>
          <h2 className="mb-3 text-lg font-semibold">{output.title}</h2>
          <ol className="space-y-2">
            {output.sentences.map((s) => {
              const isSel = s.order_index === selected;
              const blocked = s.verdict === "UNSUPPORTED" || s.verdict === "CONTRADICTED";
              return (
                <li
                  key={s.order_index}
                  onClick={() => setSelected(s.order_index)}
                  className={`cursor-pointer rounded-md border p-2 text-sm transition ${
                    isSel ? "border-blue-400 bg-blue-50" : "border-neutral-200 hover:bg-neutral-50"
                  } ${blocked ? "ring-1 ring-red-200" : ""}`}
                >
                  <p className={flagged.has(s.order_index) ? "line-through opacity-60" : ""}>
                    {s.text}
                  </p>
                  <div className="mt-1 flex items-center gap-2">
                    <Badge s={s} />
                    {s.claim_ids?.length ? (
                      <span className="text-[10px] text-blue-600">[{s.claim_ids.join(", ")}]</span>
                    ) : null}
                    <span className="ml-auto flex gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setAccepted(toggle(accepted, s.order_index));
                        }}
                        className={`rounded px-1.5 text-[11px] ${
                          accepted.has(s.order_index)
                            ? "bg-green-600 text-white"
                            : "bg-neutral-100 text-neutral-600"
                        }`}
                      >
                        ✓
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setFlagged(toggle(flagged, s.order_index));
                        }}
                        className={`rounded px-1.5 text-[11px] ${
                          flagged.has(s.order_index)
                            ? "bg-red-600 text-white"
                            : "bg-neutral-100 text-neutral-600"
                        }`}
                      >
                        ⚑
                      </button>
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>

        {/* Right: evidence for the selected sentence */}
        <div className="md:sticky md:top-4 md:self-start">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Evidence
          </h3>
          {selected == null ? (
            <p className="rounded-md border border-dashed border-neutral-300 p-4 text-sm text-neutral-500">
              Select a sentence to see the source it is grounded in.
            </p>
          ) : selectedClaims.length === 0 ? (
            <p className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              No grounding — this sentence cites no verifiable claim.
            </p>
          ) : (
            <ul className="space-y-3">
              {selectedClaims.map((c) => (
                <li key={c.key} className="rounded-md border border-neutral-200 p-3 text-sm">
                  <div className="mb-1 flex items-center gap-2 text-[11px] text-neutral-500">
                    <span className="font-mono text-blue-600">{c.key}</span>
                    <span className="rounded bg-neutral-100 px-1.5">{c.claim_type}</span>
                    <span>
                      p{c.page}
                      {c.section ? ` · ${c.section}` : ""}
                    </span>
                  </div>
                  <blockquote className="border-l-2 border-blue-300 pl-2 text-neutral-800">
                    “{c.quote}”
                  </blockquote>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
