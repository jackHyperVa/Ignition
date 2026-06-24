#!/bin/bash
# backup-ignition.sh
# Triggers a live Ignition gateway backup via gwcmd, copies the .gwbk into
# a git worktree on the 'backups' branch, then commits and pushes.
# Uses a worktree so the main working tree NEVER switches branches —
# this prevents killing the active Claude Code session.

set -e

CONTAINER="ignition"
CONTAINER_TMP="/usr/local/bin/ignition/data/backup-staging.gwbk"
TIMESTAMP=$(date +%Y-%m-%d-%H%M)
BACKUP_FILENAME="ignition-backup-${TIMESTAMP}.gwbk"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKTREE_DIR="${REPO_DIR}/.git/backup-worktree"
BRANCH="backups"

echo "=== Ignition Gateway Backup ==="
echo "Timestamp : ${TIMESTAMP}"
echo "Container : ${CONTAINER}"
echo "Branch    : ${BRANCH}"
echo ""

# --- 1. Verify container is running ---
if ! docker ps --filter "name=${CONTAINER}" --filter "status=running" --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
    echo "ERROR: Container '${CONTAINER}' is not running." >&2
    exit 1
fi

# --- 2. Trigger backup inside container ---
echo "[1/5] Running gwcmd backup inside container..."
docker exec "${CONTAINER}" /usr/local/bin/ignition/gwcmd.sh --backup "${CONTAINER_TMP}"

# --- 3. Set up worktree (main working tree never switches branches) ---
echo "[2/5] Preparing git worktree..."
git worktree remove --force "${WORKTREE_DIR}" 2>/dev/null || true

# Create backups branch locally if it doesn't exist anywhere
if ! git show-ref --quiet "refs/heads/${BRANCH}" && ! git show-ref --quiet "refs/remotes/origin/${BRANCH}"; then
    git branch "${BRANCH}" main
fi

git worktree add "${WORKTREE_DIR}" "${BRANCH}"

# --- 4. Copy backup into worktree ---
echo "[3/5] Copying backup from container..."
mkdir -p "${WORKTREE_DIR}/backups"
docker cp "${CONTAINER}:${CONTAINER_TMP}" "${WORKTREE_DIR}/backups/${BACKUP_FILENAME}"
docker exec "${CONTAINER}" rm "${CONTAINER_TMP}"

FILESIZE=$(du -sh "${WORKTREE_DIR}/backups/${BACKUP_FILENAME}" | cut -f1)
echo "      Backup size: ${FILESIZE}"

# --- 5. Commit from inside the worktree ---
echo "[4/5] Committing..."
cd "${WORKTREE_DIR}"
git add -f "backups/${BACKUP_FILENAME}"
git -c user.email="jswayze@hyper.com" -c user.name="Jack Swayze" \
    commit -m "Ignition gateway backup ${TIMESTAMP}

Live backup taken via gwcmd from container '${CONTAINER}'.
File: backups/${BACKUP_FILENAME}
Size: ${FILESIZE}

Backup covers all Ignition configuration including:
- OPC-UA connections (Simulator, RPP, RED_PDU, PLCNext_2152)
- Tag providers and tag configuration
- Gateway timer scripts
- Database connections (TimeScaleCloud)
- Project resources"

# --- 6. Push ---
echo "[5/5] Pushing to origin/${BRANCH}..."
# Token is read from ~/.git-credentials via git's credential store (never hardcoded here)
git push -u origin "${BRANCH}"

# --- 7. Clean up worktree ---
cd "${REPO_DIR}"
git worktree remove --force "${WORKTREE_DIR}"

echo ""
echo "=== Backup complete ==="
echo "Branch : ${BRANCH}"
echo "File   : backups/${BACKUP_FILENAME}"
