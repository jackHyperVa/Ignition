#!/bin/bash
# backup-ignition.sh
# Triggers a live Ignition gateway backup via gwcmd, copies the .gwbk into
# the backups/ directory, then commits and pushes to the 'backups' branch.
# Run from the repo root on the host where the 'ignition' Docker container lives.

set -e

CONTAINER="ignition"
CONTAINER_BACKUP_PATH="/usr/local/bin/ignition/data/backup-staging.gwbk"
TIMESTAMP=$(date +%Y-%m-%d-%H%M)
BACKUP_FILENAME="ignition-backup-${TIMESTAMP}.gwbk"
BACKUP_DIR="$(dirname "$0")/backups"
LOCAL_BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"
BRANCH="backups"

echo "=== Ignition Gateway Backup ==="
echo "Timestamp : ${TIMESTAMP}"
echo "Container : ${CONTAINER}"
echo "Output    : ${LOCAL_BACKUP_PATH}"
echo ""

# --- 1. Verify container is running ---
if ! docker ps --filter "name=${CONTAINER}" --filter "status=running" --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
    echo "ERROR: Container '${CONTAINER}' is not running." >&2
    exit 1
fi

# --- 2. Trigger backup inside container ---
echo "[1/5] Running gwcmd backup inside container..."
docker exec "${CONTAINER}" /usr/local/bin/ignition/gwcmd.sh --backup "${CONTAINER_BACKUP_PATH}"

# --- 3. Copy out of container ---
echo "[2/5] Copying backup to host..."
mkdir -p "${BACKUP_DIR}"
docker cp "${CONTAINER}:${CONTAINER_BACKUP_PATH}" "${LOCAL_BACKUP_PATH}"

# --- 4. Clean up temp file inside container ---
echo "[3/5] Cleaning up temp file in container..."
docker exec "${CONTAINER}" rm "${CONTAINER_BACKUP_PATH}"

FILESIZE=$(du -sh "${LOCAL_BACKUP_PATH}" | cut -f1)
echo "      Backup size: ${FILESIZE}"

# --- 5. Git: switch to backups branch, commit, push ---
echo "[4/5] Committing to git branch '${BRANCH}'..."

# Track current branch so we can return after committing backup
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Switch to backups branch (create if needed)
# Use -f to avoid blocking on untracked session/cache files
if git show-ref --quiet "refs/heads/${BRANCH}"; then
    git checkout -f "${BRANCH}"
    git pull --ff-only origin "${BRANCH}" 2>/dev/null || true
elif git show-ref --quiet "refs/remotes/origin/${BRANCH}"; then
    git checkout -f -b "${BRANCH}" "origin/${BRANCH}"
else
    git checkout -f -b "${BRANCH}" main
fi

git add -f "${LOCAL_BACKUP_PATH}"
git commit -m "Ignition gateway backup ${TIMESTAMP}

Live backup taken via gwcmd from container '${CONTAINER}'.
File: backups/${BACKUP_FILENAME}
Size: ${FILESIZE}

Backup covers all Ignition configuration including:
- OPC-UA connections (Simulator, RPP, RED_PDU, PLCNext_2152)
- Tag providers and tag configuration
- Gateway timer scripts
- Database connections (TimeScaleCloud)
- Project resources"

echo "[5/5] Pushing to origin/${BRANCH}..."
git push -u origin "${BRANCH}"

# Return to original branch
git checkout -f "${CURRENT_BRANCH}" 2>/dev/null || true

echo ""
echo "=== Backup complete ==="
echo "Branch : ${BRANCH}"
echo "File   : backups/${BACKUP_FILENAME}"
