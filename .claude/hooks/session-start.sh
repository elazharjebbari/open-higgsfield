#!/bin/bash
# Prepares a Claude Code cloud session for the Seedance 2.5 ad studio.
# Stdlib-only Python: nothing to install, just checks and folders.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

mkdir -p work outputs

python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ requis"'

if [ -n "${HF_API_KEY_ID:-}" ] && [ -n "${HF_API_KEY_SECRET:-}" ] || [ -n "${HF_KEY:-}" ] || [ -f .env ]; then
  key="clé API Higgsfield détectée"
else
  key="clé API absente : ajoutez HF_API_KEY_ID et HF_API_KEY_SECRET aux variables de l'environnement cloud"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 https://api.higgsfield.ai/ 2>/dev/null || true)
if [ -n "$code" ] && [ "$code" != "000" ]; then
  net="api.higgsfield.ai joignable"
else
  net="api.higgsfield.ai bloqué : ajoutez ce domaine à l'accès réseau de l'environnement"
fi

echo "Open Higgsfield Ad Studio (Seedance 2.5) — $key ; $net."
