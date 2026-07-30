#!/usr/bin/env bash
# UniPress DE — scripted redeploy (docs/08 P6): pull → build → migrate → up → verify.
#
#   ops/deploy.sh                  # redeploy the checked-out branch
#   ops/deploy.sh --no-pull        # rebuild + restart only (config-only change)
#   ops/deploy.sh --no-build       # restart only (env/compose change)
#   ops/deploy.sh --force-rebuild  # build --no-cache (when a cached layer is stale)
#   DOMAIN=unipress.gilbertmutai.com ops/deploy.sh   # also verify the public edge
#
# Server prerequisite in .env (pins the production overlay — nginx, no host ports):
#   COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
set -euo pipefail

cd "$(dirname "$0")/.."                      # repo root (compose file + .env live here)
export COMPOSE_PROFILES="${COMPOSE_PROFILES:-core,observability}"

PULL=1
BUILD=1
NOCACHE=0
for arg in "$@"; do
    case "$arg" in
        --no-pull)       PULL=0 ;;
        --no-build)      BUILD=0 ;;
        --force-rebuild) NOCACHE=1 ;;
        # Print the header comment block, however long it grows.
        -h|--help)       awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
        *) echo "✗ unknown argument: $arg (see --help)" >&2; exit 2 ;;
    esac
done

[[ -f .env ]] || { echo "✗ .env missing — copy .env.example and fill it in" >&2; exit 1; }

if ! grep -q 'docker-compose.prod.yml' .env; then
    echo "! .env does not pin docker-compose.prod.yml — deploying the DEV topology"
    echo "  (host ports published, no nginx/TLS). Intentional only on a laptop."
fi

echo "→ Profiles: $COMPOSE_PROFILES"

if ((PULL)); then
    echo "→ git pull --ff-only"
    git pull --ff-only
fi
echo "→ Deploying $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))"

if ((BUILD)); then
    # The frontend bakes NEXT_PUBLIC_API_BASE at build time, so any UI change
    # needs a real image rebuild — `up -d` alone would keep serving the old
    # bundle. Image IDs are recorded either side of the build so a rebuild that
    # silently changed nothing is visible rather than assumed.
    before="$(docker compose images -q frontend api 2>/dev/null | sort | tr '\n' ' ')"
    if ((NOCACHE)); then
        echo "→ Building images (--no-cache)"
        docker compose build --no-cache
    else
        echo "→ Building images"
        docker compose build
    fi
    after="$(docker compose images -q frontend api 2>/dev/null | sort | tr '\n' ' ')"
    if [[ $before == "$after" ]]; then
        echo "  (frontend/api images unchanged — no code change, or a stale cache)"
    else
        echo "  frontend/api images rebuilt"
    fi
fi

# Run migrations explicitly rather than leaning on the `migrate` one-shot that
# api/worker depend on: when its image is unchanged, compose is satisfied by the
# previous container's exit code and a new revision's migration never applies.
echo "→ alembic upgrade head"
docker compose run --rm migrate

# Assert the database actually reached the newest revision in the working tree.
# `alembic upgrade head` inside a STALE migrate image exits 0 having done nothing —
# its own "head" is the old one — and the freshly built api then writes to columns
# that do not exist. That happened: a selective `build api worker frontend` left
# migrate behind and broke generation in production. Comparing against the repo,
# not against the container's opinion, is what catches it.
expected="$(python3 - <<'PY'
import pathlib, re
revs = {}
for f in pathlib.Path("api/alembic/versions").glob("*.py"):
    t = f.read_text()
    r = re.search(r'^revision: str = "([^"]+)"', t, re.M)
    d = re.search(r'^down_revision: str \| None = (?:"([^"]+)"|None)', t, re.M)
    if r:
        revs[r.group(1)] = d.group(1) if d else None
children = {v for v in revs.values() if v}
heads = [r for r in revs if r not in children]
print(heads[0] if len(heads) == 1 else "AMBIGUOUS")
PY
)"
actual="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-unipress}" \
    -d "${POSTGRES_DB:-unipress}" -tAc 'select version_num from alembic_version' 2>/dev/null | tr -d '\r')"
if [[ $expected == AMBIGUOUS ]]; then
    echo "! multiple alembic heads in the working tree — merge them before deploying" >&2
elif [[ -n $expected && $actual != "$expected" ]]; then
    echo "✗ database is at '$actual' but the repo's head is '$expected'." >&2
    echo "  The migrate image is stale. Run: docker compose build migrate" >&2
    exit 1
else
    echo "  schema at $actual (repo head)"
fi

echo "→ Starting / refreshing services"
docker compose up -d --remove-orphans

# Recreating api/frontend gives them new container IPs. nginx resolves upstream
# names when it loads its config, so without a reload it keeps proxying to the
# old address and every /api/* request 502s — which is exactly what happened on
# the first scripted deploy. A reload re-resolves them with no dropped
# connections. (The config also re-resolves per request now; this covers the
# case where that is not yet deployed.)
if docker compose ps --services 2>/dev/null | grep -qx nginx; then
    echo "→ Reloading nginx (re-resolve upstream container IPs)"
    docker compose exec -T nginx nginx -s reload
fi

echo "→ Waiting for the API to report healthy"
healthy=0
for _ in $(seq 1 45); do
    if docker compose exec -T api python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
        healthy=1
        break
    fi
    sleep 2
done
if ((healthy)); then
    echo "✓ api /health OK"
else
    echo "✗ api did not become healthy — recent logs:" >&2
    docker compose logs --tail 40 api >&2
    exit 1
fi

# Optional end-to-end edge check: TLS + nginx + the /api prefix strip.
if [[ -n "${DOMAIN:-}" ]]; then
    echo "→ Verifying the public edge (https://$DOMAIN)"
    curl -fsS -o /dev/null "https://$DOMAIN/api/health" && echo "✓ /api/health OK"
    curl -fsS -o /dev/null "https://$DOMAIN/"           && echo "✓ / OK"

    # The frontend was built for a single origin if the served page links to
    # /api rather than a baked-in localhost. This is the check that would have
    # caught the dead "API" link, so it runs on every deploy.
    if curl -fsS "https://$DOMAIN/" | grep -q 'href="/api/'; then
        echo "✓ frontend built for single origin (links to /api)"
    else
        echo "✗ served page has no /api links — frontend built without" >&2
        echo "  NEXT_PUBLIC_API_BASE=/api. Re-run with --force-rebuild." >&2
        exit 1
    fi

    # Swagger must resolve its schema through the /api prefix (needs ROOT_PATH).
    if curl -fsS "https://$DOMAIN/api/docs" | grep -q "url: '/api/openapi.json'"; then
        echo "✓ Swagger resolves its schema under /api"
    else
        echo "! /api/docs is not pointing at /api/openapi.json — check ROOT_PATH=/api" >&2
    fi
fi

echo
docker compose ps
echo "✓ deploy complete"
