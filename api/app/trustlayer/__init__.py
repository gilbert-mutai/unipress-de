"""TrustLayer: verify each generated sentence against its cited source (docs/03 §5).

Phase 2a ships the deterministic core (numeric-mismatch, quote-overlap, a lexical
entailment proxy, confidence scoring, verdicts). Phase 2b swaps the lexical proxy
for a real NLI model and adds the LLM judge — both behind the ports here.
"""
