#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_file.sql>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "FAIL: File $BACKUP_FILE does not exist."
    exit 1
fi

echo "Restoring database from $BACKUP_FILE..."

cat "$BACKUP_FILE" | docker exec -i postgres psql -U barq_app -d barq_tasks > /dev/null

echo "PASS: Restore complete!"
exit 0