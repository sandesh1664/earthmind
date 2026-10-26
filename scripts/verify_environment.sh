#!/bin/sh
set -eu

for executable in git make uv node npm docker; do
  command -v "$executable" >/dev/null 2>&1 || {
    echo "BLOCKED: missing required executable: $executable" >&2
    exit 1
  }
done

printf 'Host: %s/%s\n' "$(uname -s)" "$(uname -m)"
if [ "$(uname -s)" = Darwin ]; then sw_vers; fi
node --version
npm --version
uv --version
git --version
docker --version
docker compose version
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || major >= 27 || (major === 22 && minor < 13)) { console.error("Node 22.13+ required; Node 22 LTS recommended"); process.exit(1); }'
architecture=$(docker info --format '{{.Architecture}}')
case "$architecture" in arm64|aarch64) ;; *)
  echo "BLOCKED: native ARM64 Docker engine required; found $architecture" >&2
  exit 1 ;;
esac
printf 'Docker engine: linux/%s\n' "$architecture"
docker info --format 'Docker memory limit: {{.MemTotal}} bytes'
df -h .
