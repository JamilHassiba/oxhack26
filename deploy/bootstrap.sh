#!/usr/bin/env bash
# Run once on a fresh Ubuntu VM as root. No cloud resources or credentials are created.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run bootstrap.sh as root on the Ubuntu VM.' >&2; exit 1; }
command -v apt-get >/dev/null || { echo 'This script targets Ubuntu/Debian.' >&2; exit 1; }
apt-get update
apt-get install -y python3 python3-venv python3-pip git curl ca-certificates xz-utils caddy
id concierge >/dev/null 2>&1 || useradd --system --home /opt/concierge --shell /usr/sbin/nologin concierge
install -d -m 0755 /opt/concierge /opt/concierge/releases
install -d -m 0750 -o root -g concierge /etc/concierge
# Node 24 LTS, installed privately; official HTTPS checksum checked before extraction.
case "$(uname -m)" in x86_64) node_arch=x64 ;; aarch64|arm64) node_arch=arm64 ;; *) echo 'Unsupported architecture.' >&2; exit 1 ;; esac
node_tmp=$(mktemp -d)
trap 'rm -rf "$node_tmp"' EXIT
curl --fail --silent --show-error --location https://nodejs.org/dist/latest-v24.x/SHASUMS256.txt -o "$node_tmp/SHASUMS256.txt"
node_archive=$(awk -v arch="$node_arch" '$2 ~ "^node-v24\\.[0-9]+\\.[0-9]+-linux-" arch "\\.tar\\.xz$" {print $2}' "$node_tmp/SHASUMS256.txt")
[[ -n "$node_archive" && "$node_archive" != *$'\n'* ]] || { echo 'Could not resolve the Node 24 archive.' >&2; exit 1; }
curl --fail --silent --show-error --location "https://nodejs.org/dist/latest-v24.x/$node_archive" -o "$node_tmp/$node_archive"
(cd "$node_tmp" && awk -v file="$node_archive" '$2 == file {print}' SHASUMS256.txt | sha256sum --check --status)
node_dir="${node_archive%.tar.xz}"
tar -xJf "$node_tmp/$node_archive" -C /opt/concierge
ln -sfn "/opt/concierge/$node_dir" /opt/concierge/node
/opt/concierge/node/bin/node --version
echo 'Bootstrap complete. Configure SSH/firewall/DNS and /etc/concierge/*.env as described in deploy/README.md.'
