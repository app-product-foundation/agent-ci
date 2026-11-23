# ADR 0002: A composite action inside the reusable workflow

- Status: accepted (2026-11-22)
- Issue: https://github.com/app-product-foundation/agent-ci/issues/2

## Context

The review needs files from this repository at the version the product pinned: the prompts and
the scripts. A reusable workflow cannot read its own repository's files at its own ref:
`actions/checkout` inside it checks out the caller, and the called workflow has no documented way
to learn the ref it was called at.

A composite action gets `github.action_path`, a copy of this repository at the action's ref.

## Decision

- `action/claude-review` (composite) runs one lane: install tools, render the prompt, run
  `claude-code-action`, print Claude's error on failure. Its scripts and `prompts/review/` are read
  through `github.action_path`, so they always match the action's code.
- `.github/workflows/claude-review.yml` (reusable) is the job skeleton: gate job, one job per lane (written out, not a matrix, so check names stay fixed when skipped),
  runner, timeout, permissions, `continue-on-error`. It uses the action by commit SHA.
- A commit cannot contain its own SHA, so that ref names the latest earlier commit that changed
  `action/` or `prompts/`. `scripts/action-ref.sh pin` writes it, and `scripts/action-ref.sh check`
  (CI) fails unless the ref is an ancestor of `HEAD` with identical `action/` and `prompts/` trees,
  and, on a release tag, unless its comment names that tag.
- Products normally call the reusable workflow. A product that needs its own job layout calls the
  action directly.

## Consequences

- Changing the action or prompts takes two commits: the change, then the re-pin.
- The pinned commit must stay reachable, which merge commits and kept branches guarantee
  (squash and rebase merges are not used).
- zizmor's `ref-version-mismatch` audit cannot pass for that one ref, because its comment names
  the release rather than the pinned commit; `.github/zizmor.yml` ignores it for
  `claude-review.yml` and the CI release-ref check covers it instead.
