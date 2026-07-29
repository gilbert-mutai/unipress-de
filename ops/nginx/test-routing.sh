#!/usr/bin/env bash
# Verify ops/nginx/conf.d/app.conf routing against echo backends: the /api prefix
# must be stripped, /grafana/ must be preserved, / must pass through, and
# /api/metrics must never reach the backend. Also checks that a recreated
# backend container (new IP) is picked up without reloading nginx.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
CERTS="$WORK/certs"
NET=unipress-nginx-test
ECHO_SCRIPT="$WORK/echo.py"

cleanup() {
    docker rm -f nginx-t api frontend grafana ipburn >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT
cleanup          # clear leftovers from an interrupted run…
mkdir -p "$WORK" # …which also removed $WORK, so put it back

cat > "$ECHO_SCRIPT" <<'PY'
import os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
NAME = os.environ.get("NAME", "backend")
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"{NAME} saw {self.path}".encode()
        self.send_response(200)
        self.send_header("content-type", "text/plain")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
HTTPServer(("", int(sys.argv[1])), H).serve_forever()
PY

# Throwaway cert so the TLS server block loads; never leaves this run.
mkdir -p "$CERTS/live/unipress.gilbertmutai.com"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
    -keyout "$CERTS/live/unipress.gilbertmutai.com/privkey.pem" \
    -out "$CERTS/live/unipress.gilbertmutai.com/fullchain.pem" \
    -subj "/CN=unipress.gilbertmutai.com" 2>/dev/null

docker network create "$NET" >/dev/null

start_echo() {  # $1 container+alias, $2 port, $3 label
    docker run -d --rm --name "$1" --network "$NET" --network-alias "$1" \
        -e NAME="$3" -v "$ECHO_SCRIPT:/echo.py:ro" python:3.12-alpine \
        python /echo.py "$2" >/dev/null
}
start_echo api      8000 api
start_echo frontend 3000 frontend
start_echo grafana  3000 grafana

docker run -d --rm --name nginx-t --network "$NET" -p 18443:443 \
    -v "$REPO/ops/nginx/conf.d:/etc/nginx/conf.d:ro" \
    -v "$CERTS:/etc/letsencrypt:ro" nginx:1.27-alpine >/dev/null
sleep 4

fail=0
check() {  # $1 path, $2 expected body substring
    got="$(curl -sk --max-time 8 "https://localhost:18443$1" || echo "REQUEST-FAILED")"
    if [[ "$got" == *"$2"* ]]; then
        printf '  ✓ %-34s → %s\n' "$1" "$got"
    else
        printf '  ✗ %-34s → %s   (wanted %q)\n' "$1" "$got" "$2"
        fail=1
    fi
}

echo "--- routing ---"
check /api/documents/123      "api saw /documents/123"
check /api/health             "api saw /health"
check "/api/documents?k=2"    "api saw /documents?k=2"
check /api/                   "api saw /"
check /                       "frontend saw /"
check /_next/static/x.css     "frontend saw /_next/static/x.css"
check /grafana/d/unipress     "grafana saw /grafana/d/unipress"

echo "--- /api/metrics must not reach the backend ---"
code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 https://localhost:18443/api/metrics)"
body="$(curl -sk --max-time 8 https://localhost:18443/api/metrics)"
if [[ $code == 404 && $body != *"api saw"* ]]; then
    printf '  ✓ /api/metrics → %s, never proxied\n' "$code"
else
    printf '  ✗ /api/metrics → %s body=%q\n' "$code" "$body"; fail=1
fi

echo "--- re-resolution: recreate the api container with a new IP, no nginx reload ---"
old_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' api)"
docker rm -f api >/dev/null
# Burn an IP so the replacement is guaranteed a different address.
docker run -d --rm --name ipburn --network "$NET" python:3.12-alpine sleep 60 >/dev/null
start_echo api 8000 api-restarted
sleep 3
new_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' api)"
echo "  api moved $old_ip -> $new_ip"
sleep 11   # outlive `valid=10s`
check /api/health "api-restarted saw /health"

echo
if ((fail)); then echo "RESULT: FAILURES"; exit 1; else echo "RESULT: all checks passed"; fi
