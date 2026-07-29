#!/usr/bin/env bash
# UniPress DE — pre-generate the demo outputs (docs/08 P6 "demo safety").
#
# Generates all five output types in both languages for a document, so that on
# demo day every combination a judge can click is already in the database. The
# API returns an existing output as an already-complete job (see
# GenerateRequest.refresh), so those clicks resolve in one round trip with no
# model call — no live rate-limit or latency risk in front of an audience.
#
#   ops/pregenerate.sh <document_id>                  # fresh LLM outputs (default)
#   ops/pregenerate.sh <document_id> --reuse          # skip combinations already present
#   API=http://localhost:8000 ops/pregenerate.sh <id> # against a local stack
#   TYPES="PRESS_RELEASE SOCIAL" LANGS=en ops/pregenerate.sh <id>
#
# Costs roughly $0.017 per output (gpt-4o + the gpt-4o-mini judge), so a full
# 5x2 sweep is about $0.20.
set -euo pipefail

API="${API:-https://unipress.gilbertmutai.com/api}"
TYPES="${TYPES:-PRESS_RELEASE ARTICLE SOCIAL EXEC_SUMMARY VIDEO_SCRIPT}"
LANGS="${LANGS:-en hu}"
TIMEOUT_POLLS="${TIMEOUT_POLLS:-90}"

DOC="${1:-}"
REFRESH=true
[[ "${2:-}" == "--reuse" ]] && REFRESH=false
if [[ -z $DOC ]]; then
    awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"
    exit 2
fi

jqp() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)" 2>/dev/null || true; }

# Fail early on a bad document rather than 10 times over.
status="$(curl -fsS --max-time 20 "$API/documents/$DOC" | jqp "d.get('status','?')")"
if [[ $status != done ]]; then
    echo "✗ document $DOC is '$status', not 'done' — ingest it first" >&2
    exit 1
fi
echo "Document $DOC (refresh=$REFRESH) via $API"

fails=0
made=0
reused=0
for t in $TYPES; do
    for l in $LANGS; do
        printf '  %-14s %s ' "$t" "$l"
        started=$SECONDS
        job="$(curl -fsS -X POST "$API/documents/$DOC/outputs" \
            -H 'content-type: application/json' \
            -d "{\"output_type\":\"$t\",\"language\":\"$l\",\"refresh\":$REFRESH}" \
            --max-time 30)" || { echo "✗ enqueue failed"; fails=$((fails + 1)); continue; }

        jid="$(printf '%s' "$job" | jqp "d.get('id','')")"
        st="$(printf '%s' "$job" | jqp "d.get('status','')")"
        stage="$(printf '%s' "$job" | jqp "d.get('stage','')")"
        if [[ -z $jid ]]; then echo "✗ no job id: $job"; fails=$((fails + 1)); continue; fi

        for _ in $(seq 1 "$TIMEOUT_POLLS"); do
            [[ $st == done || $st == failed ]] && break
            sleep 5
            j="$(curl -fsS --max-time 20 "$API/jobs/$jid")" || continue
            st="$(printf '%s' "$j" | jqp "d.get('status','')")"
            stage="$(printf '%s' "$j" | jqp "d.get('stage','')")"
            job="$j"
        done

        out="$(printf '%s' "$job" | jqp "d.get('result') or ''")"
        took=$((SECONDS - started))
        case "$st" in
            done)
                if [[ $stage == cached ]]; then
                    reused=$((reused + 1))
                    echo "· reused ${out:0:8} (${took}s)"
                else
                    made=$((made + 1))
                    echo "✓ generated ${out:0:8} (${took}s)"
                fi
                ;;
            failed)
                fails=$((fails + 1))
                echo "✗ failed: $(printf '%s' "$job" | jqp "(d.get('error') or '')[:120]")"
                ;;
            *)
                fails=$((fails + 1))
                echo "✗ still $st after $((TIMEOUT_POLLS * 5))s"
                ;;
        esac
    done
done

echo
echo "generated=$made reused=$reused failed=$fails"
((fails == 0)) || exit 1
echo "✓ every combination is now warm — demo clicks need no model call"
