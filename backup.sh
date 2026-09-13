#!/bin/bash
set -e

BACKUP_DIR="./database"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/barq_tasks_${TIMESTAMP}.sql"

echo "Creating backup for barq_tasks database..."
docker exec postgres pg_dump -U barq_app --clean --if-exists barq_tasks > "$BACKUP_FILE"

if [ -s "$BACKUP_FILE" ]; then
    echo "PASS: Backup successfully saved to $BACKUP_FILE"
    exit 0
else
    echo "FAIL: Backup failed or file is empty!"
    rm -f "$BACKUP_FILE"
    exit 1
fi