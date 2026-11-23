#!/usr/bin/env bash
# Install pinned releases of the GitHub CLI and Bun for one review lane.
#
# - gh: the review reads the PR and posts its comment with it. GitHub-hosted runners have it, but
#   the CodeBuild Lambda images do not document it, so a pinned release is always installed.
# - Bun: claude-code-action's own setup (oven-sh/setup-bun) downloads with no retry, so a 504 from
#   github.com fails the review. This fetches the same Bun with retries and hands it
#   to the action through path_to_bun_executable. Keep BUN_VERSION equal to `bun-version` in the
#   pinned claude-code-action's action.yml whenever that pin changes.
#
# Every download is checked against the release's published SHA-256. Supports linux x64 and arm64.
# Writes the gh directory to GITHUB_PATH and `bun=<path>` to GITHUB_OUTPUT.
set -euo pipefail

GH_CLI_VERSION=2.102.0
GH_CLI_SHA256_AMD64=bb766f710eef8ede859c18578c72c327597cd4c8a85b06001b1f3843c6019386
GH_CLI_SHA256_ARM64=7862c86c72f43df3a2d93ddde6f473285b4e2af61b494849846827e513ef6484
BUN_VERSION=1.3.14
BUN_SHA256_X64=951ee2aee855f08595aeec6225226a298d3fea83a3dcd6465c09cbccdf7e848f
BUN_SHA256_AARCH64=a27ffb63a8310375836e0d6f668ae17fa8d8d18b88c37c821c65331973a19a3b

: "${RUNNER_TEMP:?RUNNER_TEMP is not set}"
: "${GITHUB_PATH:?GITHUB_PATH is not set}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is not set}"

if [ "$(uname -s)" != Linux ]; then
  echo "install-tools: only Linux runners are supported (got $(uname -s))" >&2
  exit 1
fi
case "$(uname -m)" in
  x86_64 | amd64)
    gh_arch=amd64 gh_sha256=$GH_CLI_SHA256_AMD64 bun_arch=x64 bun_sha256=$BUN_SHA256_X64 ;;
  aarch64 | arm64)
    gh_arch=arm64 gh_sha256=$GH_CLI_SHA256_ARM64 bun_arch=aarch64 bun_sha256=$BUN_SHA256_AARCH64 ;;
  *)
    echo "install-tools: unsupported architecture $(uname -m)" >&2
    exit 1 ;;
esac

tools="$RUNNER_TEMP/agent-ci-tools"
mkdir -p "$tools"

download() { # url file sha256
  curl -fsSL --retry 5 --retry-all-errors --retry-delay 10 --connect-timeout 20 --max-time 120 \
    -o "$2" "$1"
  echo "$3  $2" | sha256sum --check --strict
}

gh_name="gh_${GH_CLI_VERSION}_linux_${gh_arch}"
download "https://github.com/cli/cli/releases/download/v${GH_CLI_VERSION}/${gh_name}.tar.gz" \
  "$tools/${gh_name}.tar.gz" "$gh_sha256"
tar -xzf "$tools/${gh_name}.tar.gz" -C "$tools"
echo "$tools/${gh_name}/bin" >> "$GITHUB_PATH"

bun_name="bun-linux-${bun_arch}"
download "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/${bun_name}.zip" \
  "$tools/${bun_name}.zip" "$bun_sha256"
# python3 rather than unzip, which the Lambda images do not guarantee.
python3 -I -m zipfile -e "$tools/${bun_name}.zip" "$tools"
chmod +x "$tools/${bun_name}/bun"
echo "bun=$tools/${bun_name}/bun" >> "$GITHUB_OUTPUT"

"$tools/${gh_name}/bin/gh" --version | head -n 1
echo "bun $("$tools/${bun_name}/bun" --version)"
