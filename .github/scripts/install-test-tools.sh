#!/usr/bin/env bash
# These downloads run on GitHub-hosted Linux runners, outside a developer's proxy.
set -euo pipefail

tool_root="${RUNNER_TEMP:?}/keel-test-tools"
mkdir -p "$tool_root/bin"

fetch_tool() {
  local name="$1" url="$2" digest="$3" binary="$4"
  local archive="$tool_root/$name.tar.gz" unpack="$tool_root/$name"
  mkdir -p "$unpack"
  curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
    --retry 3 --output "$archive" "$url"
  printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
  tar -xzf "$archive" -C "$unpack"
  install -m 755 "$unpack/$binary" "$tool_root/bin/$(basename "$binary")"
}

fetch_tool beads \
  https://github.com/gastownhall/beads/releases/download/v1.3.2/beads_1.3.2_linux_amd64.tar.gz \
  c6ea3281f6ff82628351b2d0967c9eb85862c8a0ec0ebc24e63e645c8b02462e bd
fetch_tool fnox \
  https://github.com/jdx/fnox/releases/download/v1.46.0/fnox-x86_64-unknown-linux-gnu.tar.gz \
  08d2f8649f968191719938e475a8d6cdd868766a61f3fb397e8e0abbb50244dc fnox
fetch_tool age \
  https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz \
  cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10 age/age
install -m 755 "$tool_root/age/age/age-keygen" "$tool_root/bin/age-keygen"
printf '%s\n' "$tool_root/bin" >> "$GITHUB_PATH"
"$tool_root/bin/bd" --version
"$tool_root/bin/fnox" --version
"$tool_root/bin/age" --version
