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
MACHINE="${MACHINE:-captain-01}"
TMP="$(mktemp -d)"
# Git Bash: hand Windows tools (node, caprover) a path they can open too
command -v cygpath >/dev/null 2>&1 && TMP="$(cygpath -m "$TMP")"
trap 'rm -rf "$TMP"' EXIT
if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi

resolve() { { curl -fsS -m 15 -H "accept: application/dns-json" "https://cloudflare-dns.com/dns-query?name=$1&type=A" || true; } | grep -o '"data":"[0-9.]*"' | head -1 | cut -d'"' -f4 || true; }
# the server's address comes from the saved CapRover login (whatever the machine is called)
CAPTAIN_HOST="$(node -e 'const j=require(require("os").homedir()+"/.config/configstore/caprover.json");const m=(j.CapMachines||[]).find(x=>x.name===process.argv[1]);if(!m){process.exit(1)}console.log(new URL(m.baseUrl).hostname)' "$MACHINE")" \
  || { echo "No CapRover login named '$MACHINE' on this computer: run 'caprover login' (or set MACHINE=<name>)."; exit 1; }
SERVER_IP="$(resolve "$CAPTAIN_HOST")"
[ -n "$SERVER_IP" ] || { echo "Could not look up $CAPTAIN_HOST"; exit 1; }
echo "CapRover server: $CAPTAIN_HOST ($SERVER_IP)"
for host in "$DOMAIN" "www.$DOMAIN"; do
  got="$(resolve "$host" || true)"
  if [ "$got" != "$SERVER_IP" ]; then
    echo "DNS not ready: $host resolves to '${got:-nothing}', expected $SERVER_IP."
    echo "Add an A record (DNS only, not proxied) for $host -> $SERVER_IP, wait for it to resolve, then re-run."
    exit 1
  fi
  echo "DNS ok: $host -> $got"
done

api() { # api <path> <json>; prints the server's answer or its error
  printf '%s' "$2" > "$TMP/body.json"
  rm -f "$TMP/out.json"
  local log
  log="$(MSYS_NO_PATHCONV=1 caprover api -n "$MACHINE" -t "$1" -m POST -d "$(cat "$TMP/body.json")" -o "$TMP/out.json" < /dev/null 2>&1 || true)"
  if echo "$log" | grep -q "successfully"; then echo "  ok"; else echo "  $(echo "$log" | grep -E 'Error Code|Message' | head -2 | tr '\n' ' ')"; fi
}

for host in "$DOMAIN" "www.$DOMAIN"; do
  echo "attach $host"; api /user/apps/appDefinitions/customdomain "{\"appName\":\"$APP\",\"customDomain\":\"$host\"}"; echo
  echo "https for $host"; api /user/apps/appDefinitions/enablecustomdomainssl "{\"appName\":\"$APP\",\"customDomain\":\"$host\"}"; echo
done

# www and the CapRover address are sent to https://$DOMAIN by the site's own nginx (deploy/nginx.conf),
# in one hop. CapRover's "redirect domain" setting is left empty: it sends https visitors to http:// first.
echo "HTTPS only; CapRover's own domain redirect off (nginx redirects to https://$DOMAIN)"
MSYS_NO_PATHCONV=1 caprover api -n "$MACHINE" -t /user/apps/appDefinitions -m GET -d '{}' -o "$TMP/apps.json" < /dev/null >/dev/null 2>&1
node -e '
const fs=require("fs");const [file,app,domain,out]=process.argv.slice(1);
const j=JSON.parse(fs.readFileSync(file,"utf8"));const d=j.data||j;const a=d.appDefinitions.find(x=>x.appName===app);
if(!a){console.error("app not found");process.exit(1)}
const keep=["appName","instanceCount","captainDefinitionRelativeFilePath","notExposeAsWebApp","forceSsl","websocketSupport","volumes","ports","envVars","containerHttpPort","description","appDeployTokenConfig","httpAuth","preDeployFunction","serviceUpdateOverride","customNginxConfig","tags"];
const up={};for(const k of keep) if(a[k]!==undefined) up[k]=a[k];
up.forceSsl=true;up.redirectDomain="";
fs.writeFileSync(out,JSON.stringify(up));' "$TMP/apps.json" "$APP" "$DOMAIN" "$TMP/update.json"
# only redirect once the apex itself is attached with HTTPS, or the site would point at nothing
node -e 'const fs=require("fs");const j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));const a=(j.data||j).appDefinitions.find(x=>x.appName===process.argv[2]);process.exit((a.customDomain||[]).some(d=>d.publicDomain===process.argv[3]&&d.hasSsl)?0:1)' "$TMP/apps.json" "$APP" "$DOMAIN" \
  || { echo "  $DOMAIN is not attached with HTTPS yet (the server may still cache the old DNS answer); re-run later."; exit 1; }
MSYS_NO_PATHCONV=1 caprover api -n "$MACHINE" -t /user/apps/appDefinitions/update -m POST -d "$(cat "$TMP/update.json")" -o "$TMP/out.json" < /dev/null >/dev/null 2>&1 && echo "  ok"

echo "rebuild pages for https://$DOMAIN and deploy"
SITE_URL="https://$DOMAIN" PYTHONIOENCODING=utf-8 "$PY" site/generate.py
./deploy.sh "$APP"
for u in "https://$DOMAIN/" "https://www.$DOMAIN/" "https://$APP.behind7proxies.com/"; do
  curl -s -o /dev/null -m 30 -w "%{http_code} -> %{url_effective}\n" -L "$u"
done
