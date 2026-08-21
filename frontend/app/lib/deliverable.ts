/** Turning a reviewed output into something a press officer can actually use.
 *
 * The review UI shows verdicts and claim ids because that is its job. What gets
 * pasted into a newsroom CMS, an email or a social composer must carry none of
 * that, just the text, shaped for where it is going, with flagged sentences gone
 * and reviewer edits applied.
 */
import { Decision, OutputDetail, SentenceRead } from "./api";

/** Overlay locally-held rulings onto the fetched sentences.
 *
 * The UI updates optimistically, so the copy and the character count must reflect
 * what the reviewer has just clicked rather than the last server response.
 */
export function withReview(
  sentences: SentenceRead[],
  decisions: Record<number, Decision>,
  edits: Record<number, string> = {},
): SentenceRead[] {
  return sentences.map((s) => ({
    ...s,
    decision: decisions[s.order_index] ?? null,
    edited_text: edits[s.order_index] ?? null,
  }));
}

/** Sentences fit to publish, in order, with edits substituted for originals. */
export function publishableSentences(output: OutputDetail): SentenceRead[] {
  return [...output.sentences]
    .sort((a, b) => a.order_index - b.order_index)
    .filter((s) => s.decision !== "flagged")
    .map((s) => (s.edited_text ? { ...s, text: s.edited_text } : s));
}

const displayText = (s: SentenceRead) => (s.edited_text || s.text).trim();

/** Plain text, shaped by output type. */
export function asPlainText(output: OutputDetail, withCitations = false): string {
  const sentences = publishableSentences(output);
  const cite = (s: SentenceRead) =>
    withCitations && s.claim_ids?.length ? ` [${s.claim_ids.join(", ")}]` : "";

  if (output.output_type === "VIDEO_SCRIPT") {
    // A script is read down the page: timecode, narration, then the caption.
    const lines = sentences.map((s) => {
      const head = s.timecode ? `${s.timecode}  ` : "";
      const onScreen = s.on_screen ? `\n    ON SCREEN: ${s.on_screen}` : "";
      const visual = s.visual ? `\n    VISUAL: ${s.visual}` : "";
      return `${head}${displayText(s)}${cite(s)}${onScreen}${visual}`;
    });
    return [output.title, "", ...lines].join("\n");
  }

  if (output.output_type === "SOCIAL") {
    // A social composer wants the post, not a headline above it.
    return sentences.map((s) => `${displayText(s)}${cite(s)}`).join("\n\n");
  }

  const paragraphs = sentences.map((s) => `${displayText(s)}${cite(s)}`);
  return [output.title, "", ...paragraphs].join("\n");
}

/** The same content as HTML, so a paste into Word or Outlook keeps its shape. */
export function asRichHtml(output: OutputDetail, withCitations = false): string {
  const esc = (t: string) =>
    t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const sentences = publishableSentences(output);
  const cite = (s: SentenceRead) =>
    withCitations && s.claim_ids?.length
      ? ` <span style="color:#666">[${esc(s.claim_ids.join(", "))}]</span>`
      : "";

  if (output.output_type === "VIDEO_SCRIPT") {
    const rows = sentences
      .map(
        (s) =>
          `<tr><td style="padding:4px 8px;white-space:nowrap"><b>${esc(s.timecode ?? "")}</b></td>` +
          `<td style="padding:4px 8px">${esc(displayText(s))}${cite(s)}</td>` +
          `<td style="padding:4px 8px;color:#7a5a00">${esc(s.on_screen ?? "")}</td></tr>`,
      )
      .join("");
    return `<h2>${esc(output.title)}</h2><table>${rows}</table>`;
  }

  const body = sentences.map((s) => `<p>${esc(displayText(s))}${cite(s)}</p>`).join("");
  const heading = output.output_type === "SOCIAL" ? "" : `<h2>${esc(output.title)}</h2>`;
  return `${heading}${body}`;
}

/** Characters a social post would occupy, for the 280 limit on X. */
export function socialLength(output: OutputDetail): number {
  return asPlainText(output).length;
}

/** Write both flavours in one operation: rich paste where supported, plain elsewhere. */
export async function copyDeliverable(
  output: OutputDetail,
  withCitations = false,
): Promise<void> {
  const text = asPlainText(output, withCitations);
  const html = asRichHtml(output, withCitations);

  // ClipboardItem is unavailable in some browsers (and over plain http), so fall
  // back to plain text rather than failing the copy outright.
  if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/plain": new Blob([text], { type: "text/plain" }),
          "text/html": new Blob([html], { type: "text/html" }),
        }),
      ]);
      return;
    } catch {
      /* fall through to plain text */
    }
  }
  await navigator.clipboard.writeText(text);
}
