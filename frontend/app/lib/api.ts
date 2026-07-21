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
}

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

export async function uploadDocument(file: File): Promise<DocumentRead> {
  const form = new FormData();
  form.append("file", file);
  return json(await fetch(`${API_BASE}/documents`, { method: "POST", body: form }));
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

export function renderUrl(outputId: string, format: "html" | "pdf"): string {
  return `${API_BASE}/documents/outputs/${outputId}/render?format=${format}`;
}

/** URL of a source page rendered to PNG, with an optional highlighted bbox. */
export function pageImageUrl(
  documentId: string,
  page: number,
  bbox?: number[] | null,
): string {
  const q = bbox && bbox.length === 4 ? `?bbox=${bbox.join(",")}` : "";
  return `${API_BASE}/documents/${documentId}/pages/${page}.png${q}`;
}
