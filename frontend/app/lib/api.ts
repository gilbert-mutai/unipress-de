// Typed client for the UniPress DE API. Single origin behind nginx in prod;
// direct to the api in local dev (NEXT_PUBLIC_API_BASE).
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Status = "pending" | "processing" | "done" | "failed";

export interface DocumentRead {
  id: string;
  filename: string;
  status: Status;
  stage: string | null;
  progress: number | null;
  page_count: number | null;
  chunk_count: number | null;
  claim_count: number | null;
  warnings: string[] | null;
  error: string | null;
}

export interface ClaimRead {
  id: string;
  key: string;
  text: string;
  claim_type: string;
  page: number;
  section: string | null;
  quote: string;
  bbox: number[] | null;
  importance: number;
  numeric: boolean;
}

export interface JobRead {
  id: string;
  status: Status;
  stage: string;
  result: string | null;
  error: string | null;
  /** Worker-reported completion, 0–100, and the phase it is in. */
  progress?: number | null;
  detail?: string | null;
}

export type Verdict =
  | "SUPPORTED"
  | "INTERPRETATION"
  | "RHETORICAL"
  | "UNSUPPORTED"
  | "CONTRADICTED";

export interface SentenceRead {
  order_index: number;
  text: string;
  role: string;
  claim_ids: string[] | null;
  section: string | null;
  timecode: string | null;
  on_screen: string | null;
  visual: string | null;
  verdict: Verdict | null;
  confidence: number | null;
  rationale: string | null;
  /** The reviewer's ruling; drives what the published copy contains. */
  decision?: Decision | null;
  /** A reviewer's rewrite, kept beside the generated text rather than replacing it. */
  edited_text?: string | null;
}

export type Decision = "accepted" | "flagged";

export interface Coverage {
  cited: string[];
  omitted_important: string[];
  dropped_limitations: string[];
  warnings: string[];
}

export interface OutputDetail {
  id: string;
  document_id: string;
  output_type: string;
  language: string;
  title: string;
  title_claim_ids?: string[] | null;
  title_verdict?: string | null;
  title_confidence?: number | null;
  title_rationale?: string | null;
  status: Status;
  coverage: Coverage | null;
  sentences: SentenceRead[];
}

export interface OutputSummary {
  id: string;
  output_type: string;
  language: string;
  title: string;
  status: Status;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

/** Upload a PDF, reporting transfer progress (0–1) when the browser can measure it.
 *
 * Uses XMLHttpRequest rather than fetch: fetch cannot report *upload* progress, and
 * on a slow link the transfer is the whole wait — a 2.5 MB paper took 12–57s from
 * Europe to this host, against ~0.15s of server-side work. Without progress the
 * screen simply sits there, which is the worst thing it can do in a demo.
 */
export function uploadDocument(
  file: File,
  onProgress?: (fraction: number) => void,
): Promise<DocumentRead> {
  const form = new FormData();
  form.append("file", file);

  return new Promise<DocumentRead>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/documents`);
    xhr.responseType = "text";

    xhr.upload.onprogress = (e) => {
      // lengthComputable is false for chunked encoding; leave the caller to show
      // an indeterminate state rather than inventing a number.
      if (e.lengthComputable && e.total > 0) onProgress?.(e.loaded / e.total);
    };
    // The bytes are gone but the server has yet to answer: hold at 100% so the
    // caller can switch to "processing" instead of appearing stuck mid-bar.
    xhr.upload.onload = () => onProgress?.(1);

    xhr.onload = () => {
      let body: unknown;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as DocumentRead);
      } else {
        const detail =
          body && typeof body === "object" && "detail" in body
            ? String((body as { detail: unknown }).detail)
            : `${xhr.status} ${xhr.statusText}`;
        reject(new Error(detail));
      }
    };
    xhr.onerror = () =>
      reject(new Error("Upload failed — the connection dropped or timed out."));
    xhr.onabort = () => reject(new Error("Upload cancelled."));
    xhr.send(form);
  });
}

export async function getDocument(id: string): Promise<DocumentRead> {
  return json(await fetch(`${API_BASE}/documents/${id}`));
}

export async function getClaims(id: string): Promise<ClaimRead[]> {
  return json(await fetch(`${API_BASE}/documents/${id}/claims`));
}

export async function generateOutput(
  id: string,
  outputType: string,
  language: string,
): Promise<JobRead> {
  return json(
    await fetch(`${API_BASE}/documents/${id}/outputs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ output_type: outputType, language }),
    }),
  );
}

export async function getJob(id: string): Promise<JobRead> {
  return json(await fetch(`${API_BASE}/jobs/${id}`));
}

export async function getOutput(outputId: string): Promise<OutputDetail> {
  return json(await fetch(`${API_BASE}/documents/outputs/${outputId}`));
}

/** `publish` is the deliverable (flagged sentences dropped, edits applied, no
 *  verdict furniture); `evidence` is the annotated record for sign-off. */
export function renderUrl(
  outputId: string,
  format: "html" | "pdf",
  view: "publish" | "evidence" = "evidence",
): string {
  return `${API_BASE}/documents/outputs/${outputId}/render?format=${format}&view=${view}`;
}

/** Discard every decision and edit on an output, restoring the generated text. */
export async function clearReviews(outputId: string): Promise<OutputDetail> {
  return json(
    await fetch(`${API_BASE}/documents/outputs/${outputId}/reviews`, { method: "DELETE" }),
  );
}

/** Record the reviewer's ruling on one sentence so it outlives the tab. */
export async function reviewSentence(
  outputId: string,
  orderIndex: number,
  body: { decision?: "accepted" | "flagged" | null; edited_text?: string | null },
): Promise<SentenceRead> {
  return json(
    await fetch(`${API_BASE}/documents/outputs/${outputId}/sentences/${orderIndex}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

/** URL of a source page rendered to PNG, with an optional highlighted bbox. */
export function pageImageUrl(
  documentId: string,
  page: number,
  bbox?: number[] | null,
  zoom?: number,
): string {
  const params = new URLSearchParams();
  if (bbox && bbox.length === 4) params.set("bbox", bbox.join(","));
  if (zoom && zoom > 2) params.set("zoom", String(Math.min(4, zoom)));
  const q = params.toString();
  return `${API_BASE}/documents/${documentId}/pages/${page}.png${q ? `?${q}` : ""}`;
}
