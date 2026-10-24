#!/usr/bin/env bash
# Deploy an explicit Git revision from the VM checkout. Never prints or sources API secrets.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run deploy.sh as root on the VM.' >&2; exit 1; }
revision="${1:?Usage: sudo deploy/deploy.sh GIT_REVISION}"
repo_root=$(git rev-parse --show-toplevel)
commit=$(git rev-parse --verify "${revision}^{commit}")
short_commit=$(git rev-parse --short=12 "$commit")
export PATH="/opt/concierge/node/bin:$PATH"
node -e 'const [major,minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) process.exit(1)' || { echo 'Install Node 24 with bootstrap.sh first.' >&2; exit 1; }
for config in /etc/concierge/api.env /etc/concierge/caddy.env; do
    [[ -f "$config" ]] || { echo "Configure $config first." >&2; exit 1; }
done
release="/opt/concierge/releases/$(date -u +%Y%m%dT%H%M%SZ)-$short_commit"
install -d -m 0755 "$release"
git -C "$repo_root" archive "$commit" | tar -x -C "$release"
python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install --quiet -r "$release/backend/requirements-evan.txt"
(cd "$release/frontend" && npm ci && VITE_DEMO_MODE=false VITE_API_BASE_URL=/api npm run build)
# Dependencies/build finish before touching the running release.
chown -R root:concierge "$release"
chmod -R o+rX "$release/frontend/dist"
# Caddy env files contain public addresses only; API secrets are never sourced here.
set -a
# shellcheck disable=SC1091
source /etc/concierge/caddy.env
set +a
caddy validate --config "$release/deploy/Caddyfile" --adapter caddyfile
previous=$(readlink -f /opt/concierge/current || true)
backup=$(mktemp -d)
for item in /etc/systemd/system/oxhack-api.service /etc/caddy/Caddyfile /etc/systemd/system/caddy.service.d/concierge.conf; do
    if [[ -f "$item" ]]; then cp "$item" "$backup/$(basename "$item")"; fi
done
rollback() {
    set +e
    echo 'Deployment failed; restoring the previous release and configuration.' >&2
    for item in /etc/systemd/system/oxhack-api.service /etc/caddy/Caddyfile /etc/systemd/system/caddy.service.d/concierge.conf; do
        if [[ -f "$backup/$(basename "$item")" ]]; then cp "$backup/$(basename "$item")" "$item"; else rm -f "$item"; fi
    done
    systemctl daemon-reload
    if [[ -n "$previous" && -d "$previous" ]]; then
        ln -sfn "$previous" /opt/concierge/current.next
        mv -Tf /opt/concierge/current.next /opt/concierge/current
        systemctl restart oxhack-api
    else
        systemctl stop oxhack-api
        rm -f /opt/concierge/current
    fi
    systemctl reload-or-restart caddy
    rm -rf "$backup"
}
trap 'rollback; exit 1' ERR
install -m 0644 "$release/deploy/oxhack-api.service" /etc/systemd/system/oxhack-api.service
install -m 0644 "$release/deploy/Caddyfile" /etc/caddy/Caddyfile
install -d -m 0755 /etc/systemd/system/caddy.service.d
cat > /etc/systemd/system/caddy.service.d/concierge.conf <<'DROPIN'
[Service]
EnvironmentFile=/etc/concierge/caddy.env
DROPIN
systemctl daemon-reload
ln -sfn "$release" /opt/concierge/current.next
mv -Tf /opt/concierge/current.next /opt/concierge/current
if ! systemctl restart oxhack-api; then rollback; exit 1; fi
healthy=0
for attempt in {1..15}; do
    if curl --fail --silent http://127.0.0.1:8000/health > "$release/health.json"; then
        if [[ "${DEPLOY_REQUIRE_DB:-1}" == 0 ]] || "$release/.venv/bin/python" -c 'import json,sys; sys.exit(json.load(open(sys.argv[1])).get("db") != "ok")' "$release/health.json"; then healthy=1; break; fi
    fi
    sleep 1
done
if [[ "$healthy" != 1 ]]; then rollback; exit 1; fi
if ! systemctl reload-or-restart caddy; then rollback; exit 1; fi
systemctl enable oxhack-api caddy
trap - ERR
rm -rf "$backup"
echo "Deployed revision $short_commit. Verify HTTPS, SPA refresh, and SSE from your browser."
