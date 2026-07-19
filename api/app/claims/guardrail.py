"""The quote-verification guardrail (docs/03 §2.3) — the trust primitive.

Every claim must carry a `quote` that is *literally present* in the source. This
module locates that quote in the source text and returns its character offsets;
if the quote cannot be found (even allowing for whitespace differences), the claim
is a hallucinated extraction and MUST be rejected. Run uniformly over both the
heuristic and LLM extraction paths so the guarantee holds regardless of source.
"""

from __future__ import annotations

import re

_WS = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    return _WS.sub(" ", text).strip()


def find_span(source: str, quote: str) -> tuple[int, int] | None:
    """Return (char_start, char_end) of `quote` within `source`, or None if absent.

    Tries an exact substring first, then a whitespace-flexible match so that
    newline/spacing differences (common in PDF text and LLM output) don't cause a
    false rejection. Offsets always index into the raw `source`, so
    `source[start:end]` is the exact verbatim span to store as the quote.
    """
    quote = quote.strip()
    if not quote:
        return None

    idx = source.find(quote)
    if idx >= 0:
        return idx, idx + len(quote)

    # Whitespace-flexible: match the quote's tokens separated by any whitespace.
    tokens = quote.split()
    if not tokens:
        return None
    pattern = r"\s+".join(re.escape(t) for t in tokens)
    match = re.search(pattern, source)
    if match:
        return match.start(), match.end()
    return None
