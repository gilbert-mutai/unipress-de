"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import EvidenceReview from "./components/EvidenceReview";
import { PipelineProgress } from "./components/PipelineProgress";
import { FileText, Sparkles, Spinner, UploadCloud } from "./components/icons";
import { Button } from "./components/ui/button";
import { Card, CardBody } from "./components/ui/card";
import { cn } from "./lib/utils";
import {
  ClaimRead,
  DocumentRead,
  OutputDetail,
  generateOutput,
  getClaims,
  getDocument,
  getJob,
  getOutput,
  uploadDocument,
} from "./lib/api";

const OUTPUT_TYPES = [
  ["PRESS_RELEASE", "Press release"],
  ["ARTICLE", "Public article"],
  ["SOCIAL", "Social post"],
  ["EXEC_SUMMARY", "Executive summary"],
  ["VIDEO_SCRIPT", "Video script"],
];

export default function Home() {
  const [doc, setDoc] = useState<DocumentRead | null>(null);
  const [claimsByKey, setClaimsByKey] = useState<Record<string, ClaimRead>>({});
  const [output, setOutput] = useState<OutputDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  // The chosen file, held while it uploads — the document does not exist yet.
  const [pending, setPending] = useState<{ name: string; size: number } | null>(null);
  const [sent, setSent] = useState(0); // fraction of bytes transferred, 0–1
  // Worker-reported generation progress, and whether the result was reused.
  const [gen, setGen] = useState<{ percent: number; detail: string | null } | null>(null);
  const [reused, setReused] = useState(false);
  const [outputType, setOutputType] = useState("PRESS_RELEASE");
  const [language, setLanguage] = useState("en");
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  async function onUpload(file: File) {
    setDoc(null);
    setClaimsByKey({});
    setOutput(null);
    setError(null);
    setBusy(true);
    // Acknowledge the choice before the first byte leaves: on a slow uplink the
    // transfer is tens of seconds, and with no feedback the page looks broken.
    setPending({ name: file.name, size: file.size });
    setSent(0);
    try {
      const uploaded = await uploadDocument(file, setSent);
      setDoc(uploaded);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    } finally {
      setPending(null);
    }
  }

  // Open an already-ingested paper with ?doc=<id> — the demo path, since those
  // documents already have their outputs generated, so a click costs no model
  // call. Deliberately only the explicit parameter: a bare URL always starts at
  // the upload box, so the full pipeline can be shown (or recorded) from
  // nothing. Nothing is remembered between visits.
  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("doc");
    if (!wanted) return;
    setBusy(true);
    getDocument(wanted)
      .then(setDoc)
      .catch(() => setBusy(false)); // unknown id: fall back to the upload box
    // Runs once on mount by design.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!doc || doc.status === "done" || doc.status === "failed") {
      if (poll.current) clearInterval(poll.current);
      setBusy(false);
      if (doc?.status === "done" && Object.keys(claimsByKey).length === 0) {
        getClaims(doc.id).then((cs) =>
          setClaimsByKey(Object.fromEntries(cs.map((c) => [c.key, c]))),
        );
      }
      return;
    }
    poll.current = setInterval(async () => {
      try {
        setDoc(await getDocument(doc.id));
      } catch (e) {
        setError(String(e));
      }
    }, 900);
    return () => {
      if (poll.current) clearInterval(poll.current);
    };
  }, [doc, claimsByKey]);

  const generate = useCallback(async () => {
    if (!doc) return;
    setError(null);
    setBusy(true);
    setOutput(null);
    setGen({ percent: 2, detail: "starting" });
    try {
      let job = await generateOutput(doc.id, outputType, language);
      // A reused output comes back already done: say so instead of flashing
      // "Generating…" for a few hundred milliseconds.
      if (job.stage === "cached") setGen({ percent: 100, detail: job.detail ?? "reused" });
      while (job.status !== "done" && job.status !== "failed") {
        await new Promise((r) => setTimeout(r, 700));
        job = await getJob(job.id);
        if (job.progress != null) setGen({ percent: job.progress, detail: job.detail ?? null });
      }
      if (job.status === "failed" || !job.result) throw new Error(job.error ?? "generation failed");
      setOutput(await getOutput(job.result));
      setReused(job.stage === "cached");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setGen(null);
    }
  }, [doc, outputType, language]);

  const uploadTitle = doc || pending ? "Source paper" : "Upload a paper";
  const uploadHint = pending && !doc
    ? "Sending the file to the server…"
    : !doc
    ? "A research paper in PDF format."
    : doc.status === "done"
      ? "Extracted into a verified claim store."
      : doc.status === "failed"
        ? "We couldn't read this PDF — try another file."
        : "Reading and analyzing your paper…";

  return (
    <main className="mx-auto max-w-content px-6 pb-16">
      {/* Hero */}
      <section className="py-7">
        <h1 className="rule-accent mt-3 max-w-3xl font-serif text-3xl font-semibold leading-[1.1] text-brand text-balance sm:text-4xl">
          Trustworthy, traceable science communication.
        </h1>
        <p className="mt-2 max-w-2xl text-muted">
          Bilingual press releases, articles, social &amp; video -{" "}
          <span className="text-ink">every claim linked to its source</span>.
        </p>
      </section>

      {error && (
        <p className="mb-6 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      )}

      {/* Step 1 — upload */}
      <Card className="animate-fade-up">
        <CardBody>
          <StepHeading n={1} title={uploadTitle} hint={uploadHint} />
          {pending && !doc ? (
            <div className="mt-4 animate-fade-in">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-muted" />
                <span className="font-medium">{pending.name}</span>
                <span className="text-sm text-muted">{formatSize(pending.size)}</span>
                <span className="ml-auto text-sm tabular-nums text-muted">
                  {/* Once the bytes are all sent the wait is the server's, not the
                      network's — say so rather than sitting at 100%. */}
                  {sent >= 1 ? "Preparing…" : `Uploading ${Math.round(sent * 100)}%`}
                </span>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-line">
                <div
                  className={cn(
                    "h-full rounded-full bg-brand transition-[width] duration-200",
                    sent >= 1 && "animate-pulse",
                  )}
                  style={{ width: `${Math.max(2, Math.round(sent * 100))}%` }}
                />
              </div>
              {pending.size > 2_000_000 && sent < 1 && (
                <p className="mt-2 text-xs text-muted">
                  {formatSize(pending.size)} over a slow connection can take a minute — a
                  smaller paper uploads in seconds.
                </p>
              )}
            </div>
          ) : !doc ? (
            <label
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                if (e.dataTransfer.files?.[0]) onUpload(e.dataTransfer.files[0]);
              }}
              className={cn(
                "mt-4 flex cursor-pointer flex-col items-center justify-center gap-2.5 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
                dragging ? "border-brand bg-brand/[0.04]" : "border-line hover:border-brand/40",
              )}
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand/10 text-brand">
                <UploadCloud className="h-6 w-6" />
              </span>
              <div>
                <div className="font-medium">Drop a PDF here, or click to choose</div>
                <div className="text-sm text-muted">Up to 30 MB · arXiv, DOAJ, PMC, repositories</div>
              </div>
              <input
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
              />
            </label>
          ) : (
            <div className="mt-4">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-muted" />
                <span className="font-medium">{doc.filename}</span>
                <StatusPill status={doc.status} />
                <label className="ml-auto cursor-pointer text-sm text-brand hover:underline">
                  Replace
                  <input
                    type="file"
                    accept="application/pdf"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
                  />
                </label>
              </div>
              <PipelineProgress doc={doc} />
            </div>
          )}
        </CardBody>
      </Card>

      {/* Step 2 — generate */}
      {doc?.status === "done" && (
        <Card className="mt-6 animate-fade-up">
          <CardBody>
            <StepHeading n={2} title="Generate an output" hint="One claim store, five audiences." />
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Select value={outputType} onChange={setOutputType} options={OUTPUT_TYPES} />
              <Select
                value={language}
                onChange={setLanguage}
                options={[
                  ["en", "English"],
                  ["hu", "Hungarian"],
                ]}
              />
              <Button variant="accent" onClick={generate} disabled={busy}>
                {busy ? <Spinner className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                {busy ? "Generating…" : "Generate"}
              </Button>
            </div>
            {busy && (
              <div className="mt-4">
                <div className="mb-1.5 flex items-center gap-2 text-sm text-ink">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-brand" />
                  {/* The phase comes from the worker, so it names the work actually
                      under way rather than a generic message. */}
                  {gen?.detail ?? "Writing and verifying every sentence against its source…"}
                  {gen ? (
                    <span className="ml-auto tabular-nums text-muted">{gen.percent}%</span>
                  ) : null}
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-line/60">
                  {gen ? (
                    <div
                      className="h-full rounded-full bg-brand transition-[width] duration-300"
                      style={{ width: `${Math.max(2, gen.percent)}%` }}
                    />
                  ) : (
                    <div className="h-full w-1/3 rounded-full bg-brand animate-indeterminate" />
                  )}
                </div>
              </div>
            )}
            {/* Sub-second results are the cache, not a fluke — worth saying, since
                it is the mechanism that keeps a demo off the critical path. */}
            {!busy && reused && output && (
              <p className="mt-3 text-sm text-muted">
                Reused an already-verified output for this type and language — no model call.
                Regenerate from scratch with the API&apos;s <code>refresh</code> flag.
              </p>
            )}
          </CardBody>
        </Card>
      )}

      {/* Step 3 — review */}
      {output && doc && (
        <Card className="mt-6 animate-fade-up">
          <CardBody>
            <StepHeading n={3} title="Review the evidence" hint="Every sentence, checked against its source." />
            <div className="mt-5">
              <EvidenceReview output={output} claimsByKey={claimsByKey} documentId={doc.id} />
            </div>
          </CardBody>
        </Card>
      )}
    </main>
  );
}

function formatSize(bytes: number): string {
  const mb = bytes / 1_000_000;
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1000))} KB`;
}

function StepHeading({ n, title, hint }: { n: number; title: string; hint: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-semibold text-brand-fg">
        {n}
      </span>
      <div>
        <h2 className="font-serif text-lg font-semibold leading-tight">{title}</h2>
        <p className="text-sm text-muted">{hint}</p>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    done: "bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  };
  const label = status === "done" ? "ingested" : status;
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-xs font-medium",
        map[status] ?? "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
      )}
    >
      {label}
    </span>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[][];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-10 rounded-lg border border-line bg-card px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
    >
      {options.map(([v, label]) => (
        <option key={v} value={v}>
          {label}
        </option>
      ))}
    </select>
  );
}
