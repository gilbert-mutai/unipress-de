"use client";

import { useEffect, useRef, useState } from "react";

// Browser calls the api directly in local dev; single-origin behind nginx in prod.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type Job = {
  id: string;
  status: "pending" | "processing" | "done" | "failed";
  stage: string;
  input_text: string;
  result: string | null;
  error: string | null;
};

const STAGES = ["queued", "ingest", "parse", "embed", "verify", "done"];

export default function Home() {
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_text: "sample paper" }),
      });
      if (!res.ok) throw new Error(`api ${res.status}`);
      setJob(await res.json());
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

  // Poll until the job reaches a terminal state.
  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed") {
      if (poll.current) clearInterval(poll.current);
      setBusy(false);
      return;
    }
    poll.current = setInterval(async () => {
      const res = await fetch(`${API_BASE}/jobs/${job.id}`);
      if (res.ok) setJob(await res.json());
    }, 700);
    return () => {
      if (poll.current) clearInterval(poll.current);
    };
  }, [job]);

  const currentIdx = job ? STAGES.indexOf(job.stage) : -1;

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">UniPress DE</h1>
      <p className="mt-2 text-neutral-600">
        Phase 0 walking skeleton — enqueue a job and watch it flow through the
        Celery pipeline.
      </p>

      <button
        onClick={submit}
        disabled={busy}
        className="mt-8 rounded-lg bg-neutral-900 px-5 py-2.5 text-white transition hover:bg-neutral-700 disabled:opacity-50"
      >
        {busy ? "Processing…" : "Run pipeline"}
      </button>

      {error && (
        <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {job && (
        <section className="mt-10">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-mono text-neutral-500">{job.id.slice(0, 8)}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                job.status === "done"
                  ? "bg-green-100 text-green-800"
                  : job.status === "failed"
                    ? "bg-red-100 text-red-800"
                    : "bg-amber-100 text-amber-800"
              }`}
            >
              {job.status}
            </span>
          </div>

          <ol className="mt-6 space-y-2">
            {STAGES.map((stage, i) => {
              const state =
                i < currentIdx ? "done" : i === currentIdx ? "active" : "todo";
              return (
                <li key={stage} className="flex items-center gap-3">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      state === "done"
                        ? "bg-green-500"
                        : state === "active"
                          ? "animate-pulse bg-amber-500"
                          : "bg-neutral-300"
                    }`}
                  />
                  <span
                    className={
                      state === "todo" ? "text-neutral-400" : "text-neutral-800"
                    }
                  >
                    {stage}
                  </span>
                </li>
              );
            })}
          </ol>

          {job.result && (
            <p className="mt-6 rounded-md bg-neutral-100 px-3 py-2 text-sm text-neutral-700">
              {job.result}
            </p>
          )}
        </section>
      )}
    </main>
  );
}
