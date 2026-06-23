#!/usr/bin/env bash
# Launch RadQuant and expose it with a public Cloudflare tunnel (no signup).
# Run in your terminal:  bash scripts/serve.sh
# Keep this terminal open; Ctrl+C stops the tunnel (the app keeps running).
set -u
cd "$(dirname "$0")/.."

CF="$HOME/cloudflared"
if [ ! -x "$CF" ]; then
  echo "→ downloading cloudflared..."
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O "$CF"
  chmod +x "$CF"
fi

# Start the Streamlit app in the background if it isn't already up.
if ! curl -s -o /dev/null --max-time 2 http://127.0.0.1:8501/healthz; then
  echo "→ starting RadQuant on :8501 ..."
  nohup streamlit run radquant/ui/app.py --server.port 8501 --server.address 0.0.0.0 \
      >/tmp/radquant_app.log 2>&1 &
  printf "→ waiting for app to boot"
  until curl -s -o /dev/null --max-time 2 http://127.0.0.1:8501/healthz; do printf "."; sleep 2; done
  echo " up."
else
  echo "→ app already running on :8501"
fi

echo "→ opening public tunnel (look for the https://*.trycloudflare.com URL below)..."
echo "========================================================================"
exec "$CF" tunnel --url http://localhost:8501
