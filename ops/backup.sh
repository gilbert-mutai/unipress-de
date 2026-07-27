#!/usr/bin/env bash
# UniPress DE — nightly backup (docs/08 P6): Postgres logical dump + Chroma and
# uploaded-PDF volume snapshots, with retention. Reproducible from the repo.
#
#   ops/backup.sh                 # run a backup now
#   BACKUP_DIR=/mnt/x ops/backup.sh
#
# Restore (Postgres): gunzip -c pg-STAMP.sql.gz | docker compose exec -T postgres \
#   psql -U unipress -d unipress
set -euo pipefail

cd "$(dirname "$0")/.."                     # repo root (compose file + .env live here)
PROJECT="unipress-de"                        # docker compose project name (compose.yml `name:`)
BACKUP_DIR="${BACKUP_DIR:-/opt/unipress-backups}"
RETAIN_DAYS="${RETAIN_DAYS:-7}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "→ Postgres dump"
docker compose exec -T postgres pg_dump -U unipress unipress | gzip > "$BACKUP_DIR/pg-$STAMP.sql.gz"

echo "→ Chroma volume snapshot"
docker run --rm -v "${PROJECT}_chromadata:/data:ro" -v "$BACKUP_DIR:/backup" alpine \
    tar czf "/backup/chroma-$STAMP.tar.gz" -C /data .

echo "→ Uploaded-PDF storage snapshot"
docker run --rm -v "${PROJECT}_storage:/data:ro" -v "$BACKUP_DIR:/backup" alpine \
    tar czf "/backup/storage-$STAMP.tar.gz" -C /data .

echo "→ Pruning backups older than ${RETAIN_DAYS} days"
find "$BACKUP_DIR" -type f -name '*.gz' -mtime +"$RETAIN_DAYS" -delete

echo "✓ backup complete → $BACKUP_DIR (stamp $STAMP)"
ls -lh "$BACKUP_DIR" | tail -n +2
