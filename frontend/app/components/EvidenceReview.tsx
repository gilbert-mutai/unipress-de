"use client";

import { useMemo, useState } from "react";
import { ClaimRead, OutputDetail, pageImageUrl, renderUrl, SentenceRead } from "../lib/api";
import { cn } from "../lib/utils";
import { AlertTriangle, Check, Download, ExternalLink, Flag } from "./icons";
import { Button } from "./ui/button";
import { Chip, VerdictBadge } from "./ui/badge";

export default function EvidenceReview({
  output,
  claimsByKey,
  documentId,
}: {
  output: OutputDetail;
  claimsByKey: Record<string, ClaimRead>;
  documentId: string;
}) {
  const [selected, setSelected] = useState<number | null>(
    output.sentences.find((s) => s.claim_ids?.length)?.order_index ?? null,
  );
  const [accepted, setAccepted] = useState<Set<number>>(new Set());
  const [flagged, setFlagged] = useState<Set<number>>(new Set());

  const toggle = (set: Set<number>, i: number, set2: (s: Set<number>) => void) => {
    const next = new Set(set);
    next.has(i) ? next.delete(i) : next.add(i);
    set2(next);
  };

  const selectedClaims = useMemo(() => {
    if (selected == null) return [];
    const s = output.sentences.find((x) => x.order_index === selected);
    return (s?.claim_ids ?? []).map((k) => claimsByKey[k]).filter(Boolean) as ClaimRead[];
  }, [selected, output, claimsByKey]);

  const primary = selectedClaims[0];

  return (
    <div>
      {output.coverage?.warnings?.length ? (
        <div className="mb-5 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{output.coverage.warnings.join(" · ")}</span>
        </div>
      ) : null}

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <a href={renderUrl(output.id, "html")} target="_blank" rel="noreferrer">
          <Button variant="outline" size="sm">
            <ExternalLink className="h-4 w-4" /> Open HTML
          </Button>
        </a>
        <a href={renderUrl(output.id, "pdf")} target="_blank" rel="noreferrer">
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4" /> PDF
          </Button>
        </a>
        <span className="ml-auto text-sm text-muted">
          {accepted.size} accepted · {flagged.size} flagged
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]">
        {/* Left — generated output */}
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand">
            {output.output_type.replace("_", " ")} · {output.language.toUpperCase()}
          </div>
          <h3 className="mb-4 font-serif text-2xl font-semibold leading-snug text-balance">
            {output.title}
          </h3>
          <div className="space-y-2.5">
            {output.sentences.map((s) => (
              <SentenceCard
                key={s.order_index}
                s={s}
                selected={s.order_index === selected}
                accepted={accepted.has(s.order_index)}
                flagged={flagged.has(s.order_index)}
                onSelect={() => setSelected(s.order_index)}
                onAccept={() => toggle(accepted, s.order_index, setAccepted)}
                onFlag={() => toggle(flagged, s.order_index, setFlagged)}
              />
            ))}
          </div>
        </div>

        {/* Right — evidence */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
            Source evidence
          </div>

          {!primary ? (
            <div className="rounded-xl border border-dashed border-line p-6 text-center text-sm text-muted">
              Select a sentence to see the exact passage it is grounded in.
            </div>
          ) : (
            <div className="animate-fade-in space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-mono font-semibold text-brand">{primary.key}</span>
                <Chip>{primary.claim_type}</Chip>
                <Chip>
                  page {primary.page}
                  {primary.section ? ` · ${primary.section}` : ""}
                </Chip>
              </div>

              <blockquote className="border-l-2 border-brand/50 bg-paper px-3 py-2 text-sm italic text-ink">
                “{primary.quote}”
              </blockquote>

              {/* The real paper page with the cited span highlighted */}
              <figure className="overflow-hidden rounded-xl border border-line bg-white">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={pageImageUrl(documentId, primary.page, primary.bbox)}
                  alt={`Source page ${primary.page}`}
                  className="w-full"
                  loading="lazy"
                />
                <figcaption className="border-t border-line bg-paper px-3 py-1.5 text-[11px] text-muted">
                  Original source · page {primary.page} — the highlighted region is the cited passage.
                </figcaption>
              </figure>

              {selectedClaims.length > 1 && (
                <div className="text-xs text-muted">
                  +{selectedClaims.length - 1} more cited claim(s):{" "}
                  {selectedClaims
                    .slice(1)
                    .map((c) => c.key)
                    .join(", ")}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SentenceCard({
  s,
  selected,
  accepted,
  flagged,
  onSelect,
  onAccept,
  onFlag,
}: {
  s: SentenceRead;
  selected: boolean;
  accepted: boolean;
  flagged: boolean;
  onSelect: () => void;
  onAccept: () => void;
  onFlag: () => void;
}) {
  const blocked = s.verdict === "UNSUPPORTED" || s.verdict === "CONTRADICTED";
  return (
    <div
      onClick={onSelect}
      className={cn(
        "cursor-pointer rounded-xl border p-3 transition-all",
        selected
          ? "border-brand/50 bg-brand/[0.04] ring-1 ring-brand/30"
          : "border-line bg-card hover:border-line hover:bg-paper",
        blocked && !selected && "border-red-200 dark:border-red-500/30",
      )}
    >
      {(s.timecode || s.section) && (
        <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-muted">
          {s.timecode && <span className="tabular-nums text-brand">{s.timecode}</span>}
          {s.section && <span>{s.section}</span>}
        </div>
      )}
      <p className={cn("text-[15px] leading-relaxed", flagged && "line-through opacity-50")}>
        {s.text}
      </p>
      {(s.on_screen || s.visual) && (
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted">
          {s.on_screen && (
            <span>
              <span className="font-medium text-ink">On-screen:</span> {s.on_screen}
            </span>
          )}
          {s.visual && (
            <span className="italic">
              <span className="font-medium not-italic text-ink">Visual:</span> {s.visual}
            </span>
          )}
        </div>
      )}
      <div className="mt-2 flex items-center gap-2">
        {s.verdict && <VerdictBadge verdict={s.verdict} confidence={s.confidence} />}
        {s.claim_ids?.length ? (
          <span className="font-mono text-[11px] text-brand">[{s.claim_ids.join(", ")}]</span>
        ) : null}
        <div className="ml-auto flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onAccept}
            aria-label="Accept"
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded-md transition-colors",
              accepted ? "bg-green-600 text-white" : "bg-line/60 text-muted hover:bg-line",
            )}
          >
            <Check className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onFlag}
            aria-label="Flag"
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded-md transition-colors",
              flagged ? "bg-red-600 text-white" : "bg-line/60 text-muted hover:bg-line",
            )}
          >
            <Flag className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
