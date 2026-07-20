"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import EvidenceReview from "./components/EvidenceReview";
import {
  ClaimRead,
  DocumentRead,
  generateOutput,
  getClaims,
  getDocument,
  getJob,
  getOutput,
  OutputDetail,
  uploadDocument,
} from "./lib/api";

const OUTPUT_TYPES = [
  ["PRESS_RELEASE", "Press release"],
  ["ARTICLE", "Article"],
  ["SOCIAL", "Social"],
  ["EXEC_SUMMARY", "Exec summary"],
  ["VIDEO_SCRIPT", "Video script"],
];

export default function Home() {
  const [doc, setDoc] = useState<DocumentRead | null>(null);
  const [claimsByKey, setClaimsByKey] = useState<Record<string, ClaimRead>>({});
  const [output, setOutput] = useState<OutputDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [outputType, setOutputType] = useState("PRESS_RELEASE");
  const [language, setLanguage] = useState("en");
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  const reset = () => {
    setDoc(null);
    setClaimsByKey({});
    setOutput(null);
    setError(null);
  };

  async function onUpload(file: File) {
    reset();
    setBusy(true);
    try {
      setDoc(await uploadDocument(file));
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

  // Poll document ingestion until terminal, then load its claims.
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

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">UniPress DE</h1>
        <p className="text-sm text-neutral-600">
          Trustworthy, traceable science communication — every claim linked to its source.
        </p>
      </header>

      {error && (
        <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {/* Step 1 — upload */}
      <section className="mb-6 rounded-xl border border-neutral-200 p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="font-medium">1 · Upload a paper</h2>
            <p className="text-sm text-neutral-500">A born-digital research PDF.</p>
          </div>
          <label className="cursor-pointer rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700">
            Choose PDF
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
            />
          </label>
        </div>

        {doc && (
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
            <span className="font-mono text-neutral-500">{doc.filename}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                doc.status === "done"
                  ? "bg-green-100 text-green-800"
                  : doc.status === "failed"
                    ? "bg-red-100 text-red-800"
                    : "bg-amber-100 text-amber-800"
              }`}
            >
              {doc.status === "done" ? "ingested" : doc.status}
            </span>
            {doc.status === "done" && (
              <span className="text-neutral-500">
                {doc.page_count} pages · {doc.chunk_count} chunks · {doc.claim_count} claims
              </span>
            )}
            {doc.status !== "done" && doc.status !== "failed" && (
              <span className="text-neutral-400">parsing → chunking → claims → embeddings…</span>
            )}
          </div>
        )}
      </section>

      {/* Step 2 — generate */}
      {doc?.status === "done" && (
        <section className="mb-6 rounded-xl border border-neutral-200 p-5">
          <h2 className="mb-3 font-medium">2 · Generate an output</h2>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={outputType}
              onChange={(e) => setOutputType(e.target.value)}
              className="rounded-md border border-neutral-300 px-3 py-2 text-sm"
            >
              {OUTPUT_TYPES.map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="rounded-md border border-neutral-300 px-3 py-2 text-sm"
            >
              <option value="en">English</option>
              <option value="hu">Hungarian</option>
            </select>
            <button
              onClick={generate}
              disabled={busy}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-50"
            >
              {busy ? "Generating…" : "Generate"}
            </button>
          </div>
        </section>
      )}

      {/* Step 3 — review */}
      {output && (
        <section className="rounded-xl border border-neutral-200 p-5">
          <h2 className="mb-4 font-medium">3 · Review the evidence</h2>
          <EvidenceReview output={output} claimsByKey={claimsByKey} />
        </section>
      )}
    </main>
  );
}
