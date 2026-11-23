#!/usr/bin/env bash
# Keep the action ref in .github/workflows/claude-review.yml in step with this commit.
#
# A reusable workflow cannot read files at its own ref, so it uses the composite action by commit
# SHA. That SHA cannot be the commit that contains it, so it points at the latest earlier commit
# that changed action/ or prompts/, and the trees must be identical.
#
#   scripts/action-ref.sh pin <vX.Y.Z>   rewrite the ref to the latest commit that changed action/
#                                        or prompts/, with a `# vX.Y.Z` comment. Commit the changes
#                                        to action/ and prompts/ first.
#   scripts/action-ref.sh check [<tag>]  fail unless the ref is an ancestor of HEAD whose action/
#                                        and prompts/ trees equal HEAD's; with a tag, also require
#                                        the comment to name that tag and HEAD to be the tag.
set -euo pipefail

workflow=.github/workflows/claude-review.yml
pattern='app-product-foundation/agent-ci/action/claude-review@([0-9a-f]{40}) # (v[0-9]+\.[0-9]+\.[0-9]+)'
trees=(action prompts)

cd "$(git rev-parse --show-toplevel)"

current() {
  # Every lane job uses the action; all of the refs must be the same.
  local line uses
  uses=$(grep -c 'app-product-foundation/agent-ci/action/claude-review@' "$workflow" || true)
  line=$(grep -oE "$pattern" "$workflow" | sort -u || true)
  if [ "$uses" -lt 1 ] || [ "$(printf '%s\n' "$line" | grep -c .)" -ne 1 ] \
    || [ "$(grep -cE "$pattern" "$workflow")" -ne "$uses" ]; then
    echo "action-ref: every 'app-product-foundation/agent-ci/action/claude-review@' in $workflow must be the same '<sha> # vX.Y.Z'" >&2
    exit 1
  fi
  [[ $line =~ $pattern ]]
  sha=${BASH_REMATCH[1]}
  version=${BASH_REMATCH[2]}
}

case "${1:-}" in
  pin)
    new_version=${2:?usage: action-ref.sh pin vX.Y.Z}
    [[ $new_version =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "action-ref: bad version $new_version" >&2; exit 1; }
    if [ -n "$(git status --porcelain -- "${trees[@]}")" ]; then
      echo "action-ref: commit the changes to ${trees[*]} first" >&2
      exit 1
    fi
    current
    new_sha=$(git log -1 --format=%H -- "${trees[@]}")
    python3 -I - "$workflow" "$sha" "$version" "$new_sha" "$new_version" <<'PY'
import sys
path, old_sha, old_version, new_sha, new_version = sys.argv[1:]
old = f"app-product-foundation/agent-ci/action/claude-review@{old_sha} # {old_version}"
new = f"app-product-foundation/agent-ci/action/claude-review@{new_sha} # {new_version}"
text = open(path, encoding="utf-8").read()  # replaces every lane job's ref
open(path, "w", encoding="utf-8").write(text.replace(old, new).replace(f"(content of {old_version})", f"(content of {new_version})"))
PY
    echo "action-ref: $workflow now uses $new_sha # $new_version"
    ;;
  check)
    tag=${2:-}
    current
    if ! git cat-file -e "$sha^{commit}" 2>/dev/null; then
      echo "action-ref: $sha is not a commit in this repository (fetch full history?)" >&2
      exit 1
    fi
    if ! git merge-base --is-ancestor "$sha" HEAD; then
      echo "action-ref: $sha is not an ancestor of HEAD" >&2
      exit 1
    fi
    for tree in "${trees[@]}"; do
      if [ "$(git rev-parse "$sha:$tree")" != "$(git rev-parse "HEAD:$tree")" ]; then
        echo "action-ref: $tree/ at $sha differs from HEAD; run scripts/action-ref.sh pin <version> and commit" >&2
        exit 1
      fi
    done
    if [ -n "$tag" ]; then
      if [ "$version" != "$tag" ]; then
        echo "action-ref: the action ref says $version, but the tag is $tag" >&2
        exit 1
      fi
      if [ "$(git rev-parse "$tag^{commit}")" != "$(git rev-parse HEAD)" ]; then
        echo "action-ref: HEAD is not $tag" >&2
        exit 1
      fi
      if ! grep -qE "^## \[?${tag#v}\]?" CHANGELOG.md; then
        echo "action-ref: CHANGELOG.md has no entry for ${tag#v}" >&2
        exit 1
      fi
    fi
    echo "action-ref: OK ($sha # $version${tag:+, tag $tag})"
    ;;
  *)
    echo "usage: action-ref.sh pin <vX.Y.Z> | check [<tag>]" >&2
    exit 2
    ;;
esac
