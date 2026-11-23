# ADR 0001: A public shared repository under app-product-foundation

- Status: accepted (2026-11-22), revised (2026-11-23)
- Issues: https://github.com/app-product-foundation/agent-ci/issues/2,
  https://github.com/app-product-foundation/agent-ci/issues/6

## Context

Every product carried its own copy of `.github/workflows/claude-review.yml`. The copies drifted
(action pin, runner, gates, the untrusted-data clause, the merge verdict, Bun and gh hardening),
and fixing the skeleton meant editing every product repository by hand.

The products live under different GitHub owners. GitHub lets a repository use a reusable workflow
or action from a private repository only under the same owner. A private shared repository would
therefore need a GitHub App token and a manual clone in every product, which gives up the
pinned, Dependabot-managed `uses:` reference that this repository exists to provide.

## Decision

Keep the skeleton in `app-product-foundation/agent-ci`, a **public** repository owned by an
organization rather than a personal account. Public visibility is what lets callers under any
owner reference it with `uses:`.

The repository holds no secrets and no product-specific content. Each product keeps
`CLAUDE_CODE_OAUTH_TOKEN` and passes it explicitly, because `secrets: inherit` does not cross
organizations. Product review viewpoints stay in each product (`AGENTS.md`, the product skill and
`.github/claude-review.md`).

Products pin a release by full commit SHA with a `# vX.Y.Z` comment, and Dependabot proposes
bumps, so a change here never silently changes every product's review.

## Why public is safe

- **Callers pin full SHAs.** A new commit or a moved tag here cannot change what a product runs
  until that product merges a bump.
- **Only organization members can write.** Outside contributors can open pull requests from forks
  but cannot push branches or tags.
- **Untrusted-data prompt contract.** Every lane's prompt treats the PR, its diff, Issues and the
  repository as data, never as instructions, and reads product rules from the base commit by
  default, so a pull request cannot change the criteria it is reviewed against.
- **Read-only tools.** Claude may only read files and run `gh pr diff/view/comment` and
  `gh issue view`; it gets no shell, no write access to code, and no other secrets.
- **Strict cost gate.** Lanes run only for non-draft, same-repository pull requests from
  `allowed-author`, and only when the caller passes the token, so fork pull requests never reach
  Claude.

## Repository settings after publishing

Applied by the owner once the repository is public:

- A ruleset on `main`: pull request required, required status checks, no force pushes or
  deletions.
- A ruleset on `v*` tags: only organization admins may create them, and no updates or deletions,
  so a released tag cannot be moved.
- Workflow runs from fork pull requests require approval for all outside contributors.
- Interaction limits as needed to keep Issues and pull requests to known contributors.

## Consequences

- The prompts and the gate logic are public. They describe review criteria, not product secrets.
- A fix ships to a product only when that product merges the bump.
- Rollouts happen per product, each with its own Issue, and must update check names that branch
  protection or merge-gate configuration reference.
