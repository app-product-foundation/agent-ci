#!/usr/bin/env bash
# Install pinned actionlint, shellcheck and zizmor for ci.yml (linux x64), checked by SHA-256.
# Writes their directory to GITHUB_PATH.
set -euo pipefail

ACTIONLINT_VERSION=1.7.12
ACTIONLINT_SHA256=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
SHELLCHECK_VERSION=0.11.0
SHELLCHECK_SHA256=8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198
ZIZMOR_VERSION=1.31.1
ZIZMOR_SHA256=d185f726bdaf92df78273217dfdd24ebcd6b0ef48cf3ce776ff5762b6e138c99

: "${RUNNER_TEMP:?RUNNER_TEMP is not set}"
: "${GITHUB_PATH:?GITHUB_PATH is not set}"
bin="$RUNNER_TEMP/lint-tools"
mkdir -p "$bin"

download() { # url file sha256
  curl -fsSL --retry 5 --retry-all-errors --retry-delay 10 --connect-timeout 20 --max-time 120 \
    -o "$2" "$1"
  echo "$3  $2" | sha256sum --check --strict
}

download "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz" \
  "$bin/actionlint.tar.gz" "$ACTIONLINT_SHA256"
tar -xzf "$bin/actionlint.tar.gz" -C "$bin" actionlint

download "https://github.com/koalaman/shellcheck/releases/download/v${SHELLCHECK_VERSION}/shellcheck-v${SHELLCHECK_VERSION}.linux.x86_64.tar.xz" \
  "$bin/shellcheck.tar.xz" "$SHELLCHECK_SHA256"
tar -xJf "$bin/shellcheck.tar.xz" -C "$bin" --strip-components=1 "shellcheck-v${SHELLCHECK_VERSION}/shellcheck"

download "https://github.com/zizmorcore/zizmor/releases/download/v${ZIZMOR_VERSION}/zizmor-x86_64-unknown-linux-gnu.tar.gz" \
  "$bin/zizmor.tar.gz" "$ZIZMOR_SHA256"
tar -xzf "$bin/zizmor.tar.gz" -C "$bin" zizmor

echo "$bin" >> "$GITHUB_PATH"
"$bin/actionlint" -version | head -n 1
"$bin/shellcheck" --version | sed -n 2p
"$bin/zizmor" --version
