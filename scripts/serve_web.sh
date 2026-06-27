#!/usr/bin/env bash
# Launch the RadQuant web stack (FastAPI backend + Next.js frontend) and expose
# it with a public Cloudflare tunnel (no signup).
#
#   bash scripts/serve_web.sh
#
# Keep this terminal open; Ctrl+C stops the tunnel. The frontend (:3000) proxies
# /api/* to the backend (:8000), so the single tunnel below serves everything.
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# Node (installed under ~/.local/node by the verification step; fall back to PATH).
if [ -x "$HOME/.local/node/bin/node" ]; then
  export PATH="$HOME/.local/node/bin:$PATH"
fi
if ! command -v node >/dev/null 2>&1; then
  echo "✗ node not found. Install Node 18+ (e.g. conda install -c conda-forge nodejs) and retry." >&2
  exit 1
fi

CF="$HOME/cloudflared"
if [ ! -x "$CF" ]; then
  echo "→ downloading cloudflared..."
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O "$CF"
  chmod +x "$CF"
fi

# ── Backend (:8000) ───────────────────────────────────────────────────────────
if ! curl -s -o /dev/null --max-time 2 http://127.0.0.1:8000/api/health; then
  echo "→ starting FastAPI backend on :8000 ..."
  nohup uvicorn backend.main:app --host 127.0.0.1 --port 8000 \
      >/tmp/radquant_backend.log 2>&1 &
  printf "→ waiting for backend"
  until curl -s -o /dev/null --max-time 2 http://127.0.0.1:8000/api/health; do printf "."; sleep 2; done
  echo " up."
else
  echo "→ backend already running on :8000"
fi

# ── Frontend (:3000) ──────────────────────────────────────────────────────────
if ! curl -s -o /dev/null --max-time 2 http://127.0.0.1:3000/; then
  cd "$ROOT/frontend"
  [ -d node_modules ] || { echo "→ installing frontend deps..."; npm install --no-audit --no-fund; }
  [ -d .next ] || { echo "→ building frontend..."; npm run build; }
  echo "→ starting Next.js frontend on :3000 ..."
  nohup npm run start >/tmp/radquant_frontend.log 2>&1 &
  printf "→ waiting for frontend"
  until curl -s -o /dev/null --max-time 2 http://127.0.0.1:3000/; do printf "."; sleep 2; done
  echo " up."
  cd "$ROOT"
else
  echo "→ frontend already running on :3000"
fi

echo "→ opening public tunnel (look for the https://*.trycloudflare.com URL below)..."
echo "========================================================================"
exec "$CF" tunnel --url http://localhost:3000
