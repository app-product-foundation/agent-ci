# Changelog

Each release says whether the review output changes. Prompt changes are behaviour changes.

## [1.0.2] - 2026-11-23

Tool restriction hardened (app-product-foundation/agent-ci#7). **Review output does not change:**
the prompts and the rendered prompt snapshots are identical to 1.0.1.

- The composite action passes `--disallowedTools "Read(./.git/**)"` to Claude Code; the deny also
  applies to Grep and Glob. In agent mode `claude-code-action` writes `github_token` into the
  origin URL in `.git/config`, so a prompt-injected pull request could otherwise ask Claude to read
  that file and quote the token in its comment. A downstream caller previously passed this deny
  itself and lost it when adopting agent-ci 1.0.1.
- New test `tests/test_action.py` fails if the deny is removed or the allowed tools widen.

## [1.0.1] - 2026-11-23

Public release (app-product-foundation/agent-ci#6). **Review output does not change:**
the prompts and the rendered prompt snapshots are identical to 1.0.0.

- The repository moved to `app-product-foundation/agent-ci`. Every self-reference, including the
  reusable workflow's composite action ref, now names the new owner. Callers pinned to 1.0.0 keep
  working through GitHub's redirect, but should bump to 1.0.1.
- Removed product-, machine- and person-specific references from comments, docs and tests. The
  `agent-merge-check` regex parity test now reads the tool's path from `AGENT_MERGE_CHECK` and is
  skipped when it is unset.
- ADR 0001 now records the public repository under app-product-foundation, why public is safe, and
  the repository settings applied after publishing.

## [1.0.0] - 2026-11-22

First release, made before the repository was published (app-product-foundation/agent-ci#3, design in app-product-foundation/agent-ci#2). The public history starts at 1.0.1, so there is no 1.0.0 tag.

- Reusable workflow `.github/workflows/claude-review.yml` with the v1 inputs: `lanes`,
  `product-skill`, `product-prompt`, `rules-ref`, `merge-verdict`, `allowed-author`, `model`,
  `runner`, `codebuild-project`, `codebuild-image`, `timeout-minutes`, `comment-language`.
- Composite action `action/claude-review`: pinned gh 2.102.0 and Bun 1.3.14 installs with SHA-256
  checks and retries (x64 and arm64), the prompt renderer, `claude-code-action` v1.0.261 with
  read-only tools and `--setting-sources user`, and the Claude error printer.
- Prompts `prompts/review/{base,code,security,verdict}.md`, merged from the review workflows that
  products previously carried. The verdict rules and marker come from the one product that already
  used a merge gate.
- Review output, compared with the product copies: every lane gets the untrusted-data rule, the
  file/line/failure-scenario/fix format and a fixed comment heading; rules are read from the base
  commit by default; comments can be written in Japanese with `comment-language: ja`.
- Defaults applied for the open decisions in #2: `comment-language: en`, `rules-ref: base`, and
  product extras in `.github/claude-review.md` with `## code`, `## security` and `## scope`.
