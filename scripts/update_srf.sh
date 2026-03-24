#!/usr/bin/env bash
# update_srf.sh — Pull latest SRF code and reinstall the Python package.
#
# /data/srf is kept read-only at runtime (Option B protection). This script
# unlocks it, pulls, reinstalls, then relocks — including on failure.
#
# Environment variables (override defaults for testing):
#   SRF_DIR   — path to the SRF git clone   (default: /data/srf)
#   VENV_PIP  — pip binary to use            (default: /data/venv/bin/pip)
#   LOG_DIR   — directory for the update log (default: /data/workspace/logs)

set -euo pipefail

SRF_DIR="${SRF_DIR:-/data/srf}"
VENV_PIP="${VENV_PIP:-/data/venv/bin/pip}"
LOG_DIR="${LOG_DIR:-/data/workspace/logs}"
LOG_FILE="${LOG_DIR}/update_srf.log"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

mkdir -p "${LOG_DIR}"

# Always relock on exit, regardless of success or failure.
relock() {
    chmod -R a-w "${SRF_DIR}" 2>/dev/null || true
}
trap relock EXIT

# Unlock for the update.
chmod -R u+w "${SRF_DIR}"

# Pull latest code.
# If FORCE_PULL is set (testing), attempt a fetch from origin to trigger failure.
if [[ "${FORCE_PULL:-0}" == "1" ]]; then
    if ! git -C "${SRF_DIR}" fetch origin 2>&1; then
        echo "${TIMESTAMP} FAILED git-pull: fetch from origin failed" >> "${LOG_FILE}"
        echo "ERROR: git fetch failed" >&2
        exit 1
    fi
fi

if ! git -C "${SRF_DIR}" pull --ff-only 2>&1; then
    echo "${TIMESTAMP} FAILED git-pull" >> "${LOG_FILE}"
    echo "ERROR: git pull --ff-only failed" >&2
    exit 1
fi

# Reinstall the package.
if ! ${VENV_PIP} install -e "${SRF_DIR}[anthropic,openai,promptledger]" 2>&1; then
    echo "${TIMESTAMP} FAILED pip-install" >> "${LOG_FILE}"
    echo "ERROR: pip install failed" >&2
    exit 1
fi

# Report the new SHA and log success.
SHA="$(git -C "${SRF_DIR}" rev-parse --short HEAD)"
echo "${TIMESTAMP} SUCCESS sha=${SHA}" >> "${LOG_FILE}"
echo "${SHA}"
