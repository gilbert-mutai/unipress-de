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
  const [outputType, setOutputType] = useState("PRESS_RELEASE");
  const [language, setLanguage] = useState("en");
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  async function onUpload(file: File) {
    setDoc(null);
    setClaimsByKey({});
    setOutput(null);
    setError(null);
    setBusy(true);
    try {
      setDoc(await uploadDocument(file));
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

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
    try {
      let job = await generateOutput(doc.id, outputType, language);
      while (job.status !== "done" && job.status !== "failed") {
        await new Promise((r) => setTimeout(r, 700));
        job = await getJob(job.id);
      }
      if (job.status === "failed" || !job.result) throw new Error(job.error ?? "generation failed");
      setOutput(await getOutput(job.result));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [doc, outputType, language]);

  const uploadTitle = doc ? "Source paper" : "Upload a paper";
  const uploadHint = !doc
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
        <h1 className="mt-3 max-w-3xl font-serif text-3xl font-semibold leading-[1.1] text-balance sm:text-4xl">
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
          {!doc ? (
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
              <Button variant="brand" onClick={generate} disabled={busy}>
                {busy ? <Spinner className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                {busy ? "Generating…" : "Generate"}
              </Button>
            </div>
            {busy && (
              <div className="mt-4">
                <div className="mb-1.5 flex items-center gap-2 text-sm text-ink">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-brand" />
                  Writing and verifying every sentence against its source…
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-line/60">
                  <div className="h-full w-1/3 rounded-full bg-brand animate-indeterminate" />
                </div>
              </div>
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

function StepHeading({ n, title, hint }: { n: number; title: string; hint: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-semibold text-paper">
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
