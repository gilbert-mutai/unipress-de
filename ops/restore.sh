#!/usr/bin/env bash
# UniPress DE — restore from an ops/backup.sh snapshot (docs/08 P6: "restore tested once").
#
#   ops/restore.sh --list                  # what is in $BACKUP_DIR
#   ops/restore.sh --latest                # restore the newest stamp
#   ops/restore.sh 20260728-031500         # restore one specific stamp
#   ONLY=pg ops/restore.sh --latest        # subset: pg,chroma,storage,mlflow
#   FORCE=1 ops/restore.sh --latest        # skip the confirmation prompt (cron/CI)
#
# DESTRUCTIVE. The live database is dropped and recreated and the selected volumes
# are wiped before extraction. Writers (api, worker, flower) are stopped for the
# duration and restarted at the end, so nothing writes mid-restore.
set -euo pipefail

cd "$(dirname "$0")/.."                     # repo root (compose file + .env live here)
PROJECT="unipress-de"                        # docker compose project name (compose.yml `name:`)
BACKUP_DIR="${BACKUP_DIR:-/opt/unipress-backups}"
ONLY="${ONLY:-pg,chroma,storage,mlflow}"
export COMPOSE_PROFILES="${COMPOSE_PROFILES:-core}"

# Credentials must match the running server, not the dump's defaults.
PGUSER_="$(grep -E '^POSTGRES_USER=' .env 2>/dev/null | cut -d= -f2-)"
PGDB_="$(grep -E '^POSTGRES_DB=' .env 2>/dev/null | cut -d= -f2-)"
PGUSER_="${PGUSER_:-unipress}"
PGDB_="${PGDB_:-unipress}"

wants() { [[ ",$ONLY," == *",$1,"* ]]; }

[[ -d $BACKUP_DIR ]] || { echo "✗ no backup dir: $BACKUP_DIR (set BACKUP_DIR)" >&2; exit 1; }

if [[ ${1:-} == --list ]]; then
    echo "Backups in $BACKUP_DIR:"
    ls -lh "$BACKUP_DIR"/*.gz 2>/dev/null || echo "  (none)"
    exit 0
fi

# --- resolve the stamp -----------------------------------------------------
case "${1:-}" in
    --latest)
        STAMP="$(ls "$BACKUP_DIR"/pg-*.sql.gz 2>/dev/null | sed 's/.*pg-\(.*\)\.sql\.gz/\1/' | sort | tail -1)"
        [[ -n $STAMP ]] || { echo "✗ no pg-*.sql.gz in $BACKUP_DIR" >&2; exit 1; }
        ;;
    "" | -h | --help)
        sed -n '2,12p' "$0"; exit 0
        ;;
    *)
        STAMP="$1"
        ;;
esac

echo "Restoring stamp $STAMP from $BACKUP_DIR"
missing=0
for name in pg chroma storage mlflow; do
    wants "$name" || continue
    if [[ $name == pg ]]; then f="$BACKUP_DIR/pg-$STAMP.sql.gz"; else f="$BACKUP_DIR/$name-$STAMP.tar.gz"; fi
    if [[ -f $f ]]; then
        echo "  ✓ $(basename "$f") ($(du -h "$f" | cut -f1))"
    else
        # An older backup predating the mlflow snapshot is expected, not fatal.
        echo "  – $(basename "$f") missing → skipping $name"
        ONLY="${ONLY//$name/}"
        [[ $name == pg ]] && missing=1
    fi
done
((missing == 0)) || { echo "✗ the Postgres dump for this stamp is missing" >&2; exit 1; }

if [[ -z ${FORCE:-} ]]; then
    echo
    echo "This OVERWRITES the live database and volumes for project '$PROJECT'."
    read -r -p "Type the stamp to confirm: " reply
    [[ $reply == "$STAMP" ]] || { echo "✗ aborted"; exit 1; }
fi

# --- quiesce the writers ---------------------------------------------------
echo "→ Stopping writers (api, worker, flower)"
docker compose stop api worker flower >/dev/null 2>&1 || true

# Volume swaps need the owning container down, or it keeps serving deleted files.
wipe_and_extract() {           # $1 = volume suffix, $2 = archive filename
    local volume="$1" archive="$2"
    docker run --rm \
        -v "${PROJECT}_${volume}:/data" \
        -v "$BACKUP_DIR:/backup:ro" \
        -e ARCHIVE="$archive" \
        alpine sh -c 'rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null; tar xzf "/backup/$ARCHIVE" -C /data'
}

# --- postgres --------------------------------------------------------------
if wants pg; then
    echo "→ Postgres: waiting for the server"
    docker compose up -d postgres >/dev/null
    for _ in $(seq 1 30); do
        docker compose exec -T postgres pg_isready -U "$PGUSER_" -d postgres >/dev/null 2>&1 && break
        sleep 2
    done

    echo "→ Postgres: recreating database '$PGDB_'"
    # WITH (FORCE) terminates leftover sessions (pg13+); the dump is a plain-SQL
    # pg_dump, so it must land in an empty database to restore cleanly.
    docker compose exec -T postgres psql -U "$PGUSER_" -d postgres -v ON_ERROR_STOP=1 -q \
        -c "DROP DATABASE IF EXISTS \"$PGDB_\" WITH (FORCE);" \
        -c "CREATE DATABASE \"$PGDB_\" OWNER \"$PGUSER_\";"

    echo "→ Postgres: loading pg-$STAMP.sql.gz"
    gunzip -c "$BACKUP_DIR/pg-$STAMP.sql.gz" \
        | docker compose exec -T postgres psql -U "$PGUSER_" -d "$PGDB_" -v ON_ERROR_STOP=1 -q
fi

# --- volumes ---------------------------------------------------------------
if wants chroma; then
    echo "→ Chroma: restoring volume"
    docker compose stop chroma >/dev/null 2>&1 || true
    wipe_and_extract chromadata "chroma-$STAMP.tar.gz"
    docker compose up -d chroma >/dev/null
fi

if wants storage; then
    echo "→ Storage: restoring uploaded PDFs"
    wipe_and_extract storage "storage-$STAMP.tar.gz"
fi

if wants mlflow; then
    echo "→ MLflow: restoring tracking store"
    docker compose stop mlflow >/dev/null 2>&1 || true
    wipe_and_extract mlflowdata "mlflow-$STAMP.tar.gz"
fi

# --- back up ---------------------------------------------------------------
echo "→ Restarting services"
docker compose up -d >/dev/null

echo "→ Verifying"
docker compose exec -T postgres psql -U "$PGUSER_" -d "$PGDB_" -tAc \
    "select 'documents=' || count(*) from documents" 2>/dev/null || true
docker compose exec -T postgres psql -U "$PGUSER_" -d "$PGDB_" -tAc \
    "select 'alembic=' || version_num from alembic_version" 2>/dev/null || true

echo "✓ restore complete (stamp $STAMP)"
