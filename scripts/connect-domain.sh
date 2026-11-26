#!/usr/bin/env bash
# Moves the site onto its own domain once DNS resolves to the CapRover server:
#   1. checks public DNS for the apex and www (both must point at the server)
#   2. attaches both domains to the CapRover app and turns on their Let's Encrypt certificates
#   3. redirects www and the behind7proxies.com address to the apex domain
#   4. rebuilds the pages with canonical URLs on the new domain and deploys
# Usage: scripts/connect-domain.sh [domain] [app]     (defaults: ontarioschoolfinder.ca ontario-schools)
# Safe to re-run: steps that are already done are reported and skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
DOMAIN="${1:-ontarioschoolfinder.ca}"
APP="${2:-ontario-schools}"
MACHINE="${MACHINE:-behind7proxies}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi

resolve() { curl -fsS -m 15 -H "accept: application/dns-json" "https://cloudflare-dns.com/dns-query?name=$1&type=A" | grep -o '"data":"[0-9.]*"' | head -1 | cut -d'"' -f4; }
SERVER_IP="$(resolve "captain.$(echo "$MACHINE" | sed 's/^behind7proxies$/behind7proxies.com/')")"
[ -n "$SERVER_IP" ] || SERVER_IP=137.184.193.6
for host in "$DOMAIN" "www.$DOMAIN"; do
  got="$(resolve "$host" || true)"
  if [ "$got" != "$SERVER_IP" ]; then
    echo "DNS not ready: $host resolves to '${got:-nothing}', expected $SERVER_IP."
    echo "Add an A record (DNS only, not proxied) for $host -> $SERVER_IP, wait for it to resolve, then re-run."
    exit 1
  fi
  echo "DNS ok: $host -> $got"
done

api() { # api <path> <json>
  printf '%s' "$2" > "$TMP/body.json"
  MSYS_NO_PATHCONV=1 caprover api -n "$MACHINE" -t "$1" -m POST -d "$(cat "$TMP/body.json")" -o "$TMP/out.json" >/dev/null 2>&1 || true
  cat "$TMP/out.json" 2>/dev/null || true
}

for host in "$DOMAIN" "www.$DOMAIN"; do
  echo "attach $host"; api /user/apps/appDefinitions/customdomain "{\"appName\":\"$APP\",\"customDomain\":\"$host\"}"; echo
  echo "https for $host"; api /user/apps/appDefinitions/enablecustomdomainssl "{\"appName\":\"$APP\",\"customDomain\":\"$host\"}"; echo
done

echo "redirect every other address to https://$DOMAIN"
MSYS_NO_PATHCONV=1 caprover api -n "$MACHINE" -t /user/apps/appDefinitions -m GET -d '{}' -o "$TMP/apps.json" >/dev/null 2>&1
node -e '
const fs=require("fs");const [file,app,domain,out]=process.argv.slice(1);
const j=JSON.parse(fs.readFileSync(file,"utf8"));const d=j.data||j;const a=d.appDefinitions.find(x=>x.appName===app);
if(!a){console.error("app not found");process.exit(1)}
const keep=["appName","instanceCount","captainDefinitionRelativeFilePath","notExposeAsWebApp","forceSsl","websocketSupport","volumes","ports","envVars","containerHttpPort","description","appDeployTokenConfig","httpAuth","preDeployFunction","serviceUpdateOverride","customNginxConfig","tags"];
const up={};for(const k of keep) if(a[k]!==undefined) up[k]=a[k];
up.forceSsl=true;up.redirectDomain=domain;
fs.writeFileSync(out,JSON.stringify(up));' "$TMP/apps.json" "$APP" "$DOMAIN" "$TMP/update.json"
MSYS_NO_PATHCONV=1 caprover api -n "$MACHINE" -t /user/apps/appDefinitions/update -m POST -d "$(cat "$TMP/update.json")" -o "$TMP/out.json" >/dev/null 2>&1
cat "$TMP/out.json"; echo

echo "rebuild pages for https://$DOMAIN and deploy"
SITE_URL="https://$DOMAIN" PYTHONIOENCODING=utf-8 "$PY" site/generate.py
./deploy.sh "$APP"
for u in "https://$DOMAIN/" "https://www.$DOMAIN/" "https://$APP.behind7proxies.com/"; do
  curl -s -o /dev/null -m 30 -w "%{http_code} -> %{url_effective}\n" -L "$u"
done
