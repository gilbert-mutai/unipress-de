"use client";

import { useMemo, useState } from "react";
import {
  ClaimRead,
  Decision,
  OutputDetail,
  pageImageUrl,
  renderUrl,
  reviewSentence,
  SentenceRead,
} from "../lib/api";
import { copyDeliverable, socialLength, withDecisions } from "../lib/deliverable";
import { cn } from "../lib/utils";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Download,
  ExternalLink,
  Copy,
  Flag,
  Minus,
  Plus,
} from "./icons";
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
  // Decisions live on the server now; this mirrors them so the UI stays instant.
  const [decisions, setDecisions] = useState<Record<number, Decision>>(() =>
    Object.fromEntries(
      output.sentences.filter((s) => s.decision).map((s) => [s.order_index, s.decision as Decision]),
    ),
  );
  const [copied, setCopied] = useState<"text" | "cited" | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  // An omitted claim has no sentence to select, so the evidence panel can also be
  // focused on a claim key directly — that is how a reviewer inspects what was
  // left out and where it sits in the paper.
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const [showOmissions, setShowOmissions] = useState(false);

  const omissions = useMemo(() => {
    const c = output.coverage;
    if (!c) return [];
    const seen = new Set<string>();
    const rows: { key: string; claim: ClaimRead | undefined; kind: "caveat" | "important" }[] = [];
    for (const key of c.dropped_limitations ?? []) {
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push({ key, claim: claimsByKey[key], kind: "caveat" });
    }
    for (const key of c.omitted_important ?? []) {
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push({ key, claim: claimsByKey[key], kind: "important" });
    }
    return rows;
  }, [output.coverage, claimsByKey]);

  const counts = useMemo(
    () => ({
      accepted: Object.values(decisions).filter((d) => d === "accepted").length,
      flagged: Object.values(decisions).filter((d) => d === "flagged").length,
    }),
    [decisions],
  );

  // The published copy reflects decisions, so the count updates with them.
  const chars = useMemo(
    () => socialLength({ ...output, sentences: withDecisions(output.sentences, decisions) }),
    [output, decisions],
  );

  /** Toggle a ruling, optimistically — then persist it. */
  const rule = async (orderIndex: number, want: Decision) => {
    const next = decisions[orderIndex] === want ? null : want;
    setDecisions((d) => {
      const copy = { ...d };
      if (next) copy[orderIndex] = next;
      else delete copy[orderIndex];
      return copy;
    });
    try {
      await reviewSentence(output.id, orderIndex, { decision: next });
    } catch {
      // Roll back rather than show a decision that was not saved: the export
      // obeys the server, so a silent divergence would publish the wrong text.
      setDecisions((d) => {
        const copy = { ...d };
        const before = decisions[orderIndex];
        if (before) copy[orderIndex] = before;
        else delete copy[orderIndex];
        return copy;
      });
      setSaveError("Could not save that decision — check the connection and try again.");
    }
  };

  const copy = async (withCitations: boolean) => {
    const shaped = { ...output, sentences: withDecisions(output.sentences, decisions) };
    try {
      await copyDeliverable(shaped, withCitations);
      setCopied(withCitations ? "cited" : "text");
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setSaveError("Copying failed — your browser blocked clipboard access.");
    }
  };

  const selectedClaims = useMemo(() => {
    if (focusKey) {
      const c = claimsByKey[focusKey];
      return c ? [c] : [];
    }
    if (selected == null) return [];
    const s = output.sentences.find((x) => x.order_index === selected);
    return (s?.claim_ids ?? []).map((k) => claimsByKey[k]).filter(Boolean) as ClaimRead[];
  }, [focusKey, selected, output, claimsByKey]);

  // Selecting a sentence and inspecting an omission are mutually exclusive views
  // of the same panel.
  const selectSentence = (i: number) => {
    setFocusKey(null);
    setSelected(i);
  };
  const inspectOmission = (key: string) => {
    setFocusKey(key);
    setZoom(1);
  };

  const primary = selectedClaims[0];

  return (
    <div>
      {output.coverage?.warnings?.length ? (
        <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
          <button
            onClick={() => setShowOmissions((v) => !v)}
            disabled={!omissions.length}
            className="flex w-full items-start gap-2 px-4 py-3 text-left"
            aria-expanded={showOmissions}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{output.coverage.warnings.join(" · ")}</span>
            {omissions.length ? (
              <span className="ml-auto flex shrink-0 items-center gap-1 whitespace-nowrap font-medium underline decoration-dotted">
                {showOmissions ? "Hide" : "Show which"}
                <ChevronDown
                  className={cn("h-4 w-4 transition-transform", showOmissions && "rotate-180")}
                />
              </span>
            ) : null}
          </button>

          {showOmissions && (
            <ul className="animate-fade-in space-y-2 border-t border-amber-200 px-4 py-3 dark:border-amber-500/30">
              {omissions.map(({ key, claim, kind }) => (
                <li key={key}>
                  <button
                    onClick={() => inspectOmission(key)}
                    disabled={!claim}
                    className={cn(
                      "w-full rounded-lg border border-amber-200/70 bg-white/60 px-3 py-2 text-left transition-colors dark:border-amber-500/20 dark:bg-black/10",
                      claim && "hover:border-amber-400 dark:hover:border-amber-500/50",
                      focusKey === key && "border-amber-500 ring-1 ring-amber-500/40",
                    )}
                  >
                    <span className="flex flex-wrap items-center gap-1.5 text-[11px]">
                      <span className="font-mono font-semibold">{key}</span>
                      <Chip>{kind === "caveat" ? "caveat dropped" : "high importance"}</Chip>
                      {claim ? <Chip>{claim.claim_type}</Chip> : null}
                      {claim ? <Chip>page {claim.page}</Chip> : null}
                    </span>
                    {claim ? (
                      <span className="mt-1 block text-xs italic leading-snug text-ink/80 dark:text-amber-100/80">
                        “{claim.quote.length > 220 ? `${claim.quote.slice(0, 220)}…` : claim.quote}”
                      </span>
                    ) : (
                      <span className="mt-1 block text-xs">
                        claim not loaded — reopen the document to inspect it
                      </span>
                    )}
                  </button>
                </li>
              ))}
              <li className="pt-1 text-[11px]">
                These claims are in the paper but not in this output. Select one to see it
                highlighted in the source, then edit the draft if it belongs.
              </li>
            </ul>
          )}
        </div>
      ) : null}

      {/* Two purposes, kept apart: what you publish, and what you keep as the
          record. Offering only the annotated version left no usable output. */}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Button variant="accent" size="sm" onClick={() => copy(false)}>
          <Copy className="h-4 w-4" /> {copied === "text" ? "Copied" : "Copy text"}
        </Button>
        <Button variant="outline" size="sm" onClick={() => copy(true)}>
          <Copy className="h-4 w-4" />
          {copied === "cited" ? "Copied" : "Copy with citations"}
        </Button>
        <a href={renderUrl(output.id, "pdf", "publish")} target="_blank" rel="noreferrer">
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4" /> Publish PDF
          </Button>
        </a>
        <a href={renderUrl(output.id, "html", "evidence")} target="_blank" rel="noreferrer">
          <Button variant="ghost" size="sm">
            <ExternalLink className="h-4 w-4" /> Evidence record
          </Button>
        </a>
        <span className="ml-auto text-sm text-muted">
          {counts.accepted} accepted · {counts.flagged} flagged
          {counts.flagged ? " · excluded from the published copy" : ""}
        </span>
      </div>

      {saveError && (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
          {saveError}
        </p>
      )}

      {output.output_type === "SOCIAL" && (
        <p className="mb-4 text-xs text-muted">
          {chars} characters — {chars <= 280 ? "fits X" : `${chars - 280} over the X limit`}; well
          within LinkedIn.
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]">
        {/* Left — generated output */}
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand">
            {output.output_type.replace("_", " ")} · {output.language.toUpperCase()}
          </div>
          <h3 className="font-serif text-2xl font-semibold leading-snug text-balance">
            {output.title}
          </h3>
          {/* The headline is verified like any factual sentence — it is the line most
              likely to be quoted, so its verdict is shown alongside it. */}
          {output.title_verdict && (
            <div className="mb-4 mt-1.5 flex flex-wrap items-center gap-2">
              <VerdictBadge
                verdict={output.title_verdict}
                confidence={output.title_confidence ?? undefined}
              />
              {output.title_claim_ids?.length ? (
                <span className="font-mono text-[11px] text-brand">
                  [{output.title_claim_ids.join(", ")}]
                </span>
              ) : (
                <span className="text-[11px] text-muted">headline cites no claim</span>
              )}
              {output.title_rationale && (
                <span className="text-[11px] text-muted">· {output.title_rationale}</span>
              )}
            </div>
          )}
          {!output.title_verdict && <div className="mb-4" />}
          <div className="space-y-2.5">
            {output.sentences.map((s) => (
              <SentenceCard
                key={s.order_index}
                s={s}
                selected={s.order_index === selected}
                accepted={decisions[s.order_index] === "accepted"}
                flagged={decisions[s.order_index] === "flagged"}
                onSelect={() => selectSentence(s.order_index)}
                onAccept={() => rule(s.order_index, "accepted")}
                onFlag={() => rule(s.order_index, "flagged")}
              />
            ))}
          </div>
        </div>

        {/* Right — evidence */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted">
            {focusKey ? "Omitted claim" : "Source evidence"}
            {focusKey ? (
              <button
                onClick={() => setFocusKey(null)}
                className="ml-auto font-medium normal-case tracking-normal text-brand underline decoration-dotted"
              >
                back to the draft
              </button>
            ) : null}
          </div>

          {focusKey ? (
            <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
              This claim is in the paper but was left out of the output.
            </p>
          ) : null}

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
              <figure className="rounded-xl border border-line bg-white">
                <div className="flex items-center gap-1.5 border-b border-line bg-paper px-2 py-1.5">
                  <span className="mr-auto text-[11px] text-muted">
                    Page {primary.page} · highlighted region is the cited passage
                  </span>
                  <button
                    onClick={() => setZoom((z) => Math.max(1, +(z - 0.5).toFixed(1)))}
                    disabled={zoom <= 1}
                    aria-label="Zoom out"
                    className="flex h-6 w-6 items-center justify-center rounded-md bg-line/60 text-muted transition-colors hover:bg-line disabled:opacity-40"
                  >
                    <Minus className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setZoom(1)}
                    className="rounded-md bg-line/60 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-muted transition-colors hover:bg-line"
                    aria-label="Reset zoom"
                  >
                    {Math.round(zoom * 100)}%
                  </button>
                  <button
                    onClick={() => setZoom((z) => Math.min(4, +(z + 0.5).toFixed(1)))}
                    disabled={zoom >= 4}
                    aria-label="Zoom in"
                    className="flex h-6 w-6 items-center justify-center rounded-md bg-line/60 text-muted transition-colors hover:bg-line disabled:opacity-40"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
                {/* Scroll container: magnified pages are panned, not squeezed. */}
                <div className={cn("max-h-[70vh] overflow-auto", zoom > 1 && "cursor-move")}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    // Past 2x the request asks the server for a higher-resolution
                    // render, so magnifying reveals detail instead of enlarging
                    // the same pixels. The first load stays at the default.
                    src={pageImageUrl(documentId, primary.page, primary.bbox, zoom * 2)}
                    alt={`Source page ${primary.page}`}
                    style={{ width: `${zoom * 100}%` }}
                    className="max-w-none"
                    loading="lazy"
                  />
                </div>
                <figcaption className="border-t border-line bg-paper px-3 py-1.5 text-[11px] text-muted">
                  Original source — zoom to read the surrounding text.
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
      {/* Why the verdict fell where it did. Shown for anything short of clearly
          supported, because that is when a reviewer needs the reason — the
          adjudicating model's own words, not a generic label. */}
      {s.rationale && s.verdict !== "SUPPORTED" && s.verdict !== "RHETORICAL" ? (
        <p
          className={cn(
            "mt-1.5 border-l-2 pl-2 text-xs leading-snug",
            blocked ? "border-red-300 text-red-700 dark:text-red-300" : "border-line text-muted",
          )}
        >
          {s.rationale}
        </p>
      ) : null}
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
