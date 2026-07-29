#!/usr/bin/env bash
# UniPress DE — nightly backup (docs/08 P6): Postgres logical dump + Chroma and
# uploaded-PDF volume snapshots, with retention. Reproducible from the repo.
#
#   ops/backup.sh                 # run a backup now
#   BACKUP_DIR=/mnt/x ops/backup.sh
#
# Restore: ops/restore.sh --latest   (drops + reloads the DB, swaps the volumes)
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

# The eval history (MLflow runs + artifacts) is demo evidence, so it is backed up
# too. Absent on hosts that never ran the `ml` profile — skip rather than fail.
if docker volume inspect "${PROJECT}_mlflowdata" >/dev/null 2>&1; then
    echo "→ MLflow tracking-store snapshot"
    docker run --rm -v "${PROJECT}_mlflowdata:/data:ro" -v "$BACKUP_DIR:/backup" alpine \
        tar czf "/backup/mlflow-$STAMP.tar.gz" -C /data .
else
    echo "→ MLflow volume absent — skipped"
fi

echo "→ Pruning backups older than ${RETAIN_DAYS} days"
find "$BACKUP_DIR" -type f -name '*.gz' -mtime +"$RETAIN_DAYS" -delete

echo "✓ backup complete → $BACKUP_DIR (stamp $STAMP)"
ls -lh "$BACKUP_DIR" | tail -n +2
