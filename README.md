# agent-ci

Shared CI skeleton for product repositories: a reusable Claude review workflow, the review
prompts, and their helpers. Design: [#2](https://github.com/app-product-foundation/agent-ci/issues/2).

The **skeleton** of the Claude reviews lives here: gates, runner selection, tool installs, the
`claude-code-action` pin, the review contract and the merge verdict format. The **product's review
viewpoints** stay in the product: `AGENTS.md`, `.agents/skills/<product>-dev/SKILL.md`, and an
optional `.github/claude-review.md`.

Each pull request gets two review lanes, each posting exactly one comment:

| Lane | Check name | Comment heading | Focus |
|---|---|---|---|
| `code` | `<caller job> / Claude review` | `Claude review` | correctness bugs, anemic domain models, layering, DRY, Atomic Design |
| `security` | `<caller job> / Claude security review` | `Security review` | high-confidence, exploitable vulnerabilities only |

The reviews never block a merge: lanes use `continue-on-error`, and a `HOLD` verdict does not fail
them. They run only for non-draft, same-repository pull requests that `allowed-author` opened and
pushed, and only when `CLAUDE_CODE_OAUTH_TOKEN` is passed. Without the token the
`Claude review gate` job prints a notice and no lane runs.

## Adopting it

Add `.github/workflows/claude-review.yml` to the product. It owns the triggers; everything else
comes from here:

```yaml
name: Claude review
on:
  pull_request:
    branches: [dev]
    types: [opened, synchronize, ready_for_review, reopened]
    # paths: [...]            # optional, product-owned
concurrency:
  group: claude-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true
permissions:
  contents: read
  pull-requests: write
  issues: read
jobs:
  claude:
    uses: app-product-foundation/agent-ci/.github/workflows/claude-review.yml@<SHA of v1.0.0> # v1.0.0
    with:
      product-skill: .agents/skills/<product>-dev/SKILL.md
      merge-verdict: false
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

Pin the full commit SHA of the release tag, with the tag as a comment, as for every other action:

```sh
gh api repos/app-product-foundation/agent-ci/commits/v1.0.0 --jq .sha
```

Then:

1. Create the token with `claude setup-token` and store it with
   `gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo <owner>/<repo>`.
   `secrets: inherit` does not cross organizations, so the caller passes the secret explicitly.
2. Let Dependabot propose release bumps (`package-ecosystem: github-actions`).
3. Update anything that names the old check: branch protection, merge-gate configuration (for
   example `.agents/agent-merge.json` `required_checks`), and review-coverage workflows. Checks are now reported as
   `claude / Claude review` and `claude / Claude security review` (`<caller job> / <lane job>`).

A product that needs its own job layout can call the composite action directly:
`uses: app-product-foundation/agent-ci/action/claude-review@<SHA> # vX.Y.Z` after `actions/checkout` with
`fetch-depth: 0` and `persist-credentials: false`. See [`action/claude-review/action.yml`](action/claude-review/action.yml).

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `lanes` | `["code","security"]` | Lanes to run, as a JSON list. |
| `product-skill` | `""` | Path to `.agents/skills/<product>-dev/SKILL.md`. |
| `product-prompt` | `.github/claude-review.md` | Optional product prompt; see below. |
| `rules-ref` | `base` | Where `AGENTS.md`, the skill and `product-prompt` are read from: `base` (the PR's base commit, recommended) or `head`. |
| `merge-verdict` | `false` | Append the [merge verdict](prompts/review/verdict.md) that `agent-merge-check` reads. |
| `allowed-author` | `Kazy1014` | The only PR author and actor the reviews run for. Callers under another owner set their own. |
| `model` | `claude-sonnet-5-5` | Claude model. |
| `runner` | `"ubuntu-latest"` | `runs-on` as JSON: a string or a list of labels. A bare label also works. |
| `codebuild-project` | `""` | When set, run on `codebuild-<project>-<run id>-<attempt>` with `image:<codebuild-image>` instead of `runner`. |
| `codebuild-image` | `arm-lambda-nodejs24` | CodeBuild image label. |
| `timeout-minutes` | `0` | Lane timeout; `0` means 20, or 13 with `codebuild-project` (Lambda stops a build after 15 minutes). |
| `comment-language` | `en` | `en` or `ja`. The verdict lines stay in English. |

Secret: `CLAUDE_CODE_OAUTH_TOKEN` (optional; without it the reviews skip).

The lane jobs need `contents: read`, `pull-requests: write` and `issues: read`, so the caller must
grant at least those.

### Product prompt

`.github/claude-review.md` adds product-specific viewpoints without forking the skeleton. Its
level-two sections are appended to the matching lane; anything before the first section is
ignored, and other sections produce a warning:

```markdown
## code
Extra correctness and design rules for this product.

## security
The product's own attack surface, for example "any query not scoped to the caller's tenant id is an IDOR".

## scope
Paths to review or ignore; added to every lane.
```

This repository's own [`.github/claude-review.md`](.github/claude-review.md) is an example.

### Rules from the base commit

With `rules-ref: base`, the action adds the PR's base commit as a separate Git worktree and tells
Claude to read `AGENTS.md`, the product skill and the product prompt from there. A pull request
therefore cannot change the criteria it is reviewed against; a PR that edits `AGENTS.md` is
reviewed against the previous rules, and its edit is reviewed as code.

Claude Code also runs with `--setting-sources user`, so it does not load `CLAUDE.md` or `.claude/`
settings from the checkout either.

## How the prompt is built

[`render-prompt.py`](action/claude-review/scripts/render-prompt.py) writes the prompt in a fixed
order, with plain `{{MARKER}}` replacement and no templating engine:

1. Context: repository, PR number, base branch, head SHA, lane.
2. [`prompts/review/base.md`](prompts/review/base.md): the contract shared by every lane
   (verified findings only, untrusted data, the comment as the final reply, a comment even
   without findings).
3. [`code.md`](prompts/review/code.md) or [`security.md`](prompts/review/security.md).
4. Product rules: `AGENTS.md`, the product skill, and the product prompt's lane and `scope` sections.
5. [`verdict.md`](prompts/review/verdict.md), only with `merge-verdict: true`. Its closing marker,
   `<!-- claude-review slug=<lane> sha=<head sha> verdict=PASS|HOLD -->`, is a contract with
   `agent-merge-check`, a merge gate that parses this marker; `tests/` holds a copy of its regex.

## Versioning

Releases are SemVer tags `vX.Y.Z`; there is no moving `v1` tag. A breaking change to inputs, the
verdict marker or check names is a major release. A prompt change changes review output, so it is
listed in [`CHANGELOG.md`](CHANGELOG.md) even when it is a minor release.

The reusable workflow uses the composite action by commit SHA. A commit cannot contain its own
SHA, so the ref points at the latest earlier commit that changed `action/` or `prompts/`, and CI
checks that those trees are identical. To change the action or prompts:

1. Commit the change to `action/` or `prompts/` (and `tests/snapshots/`).
2. Run `scripts/action-ref.sh pin vX.Y.Z` with the next release and commit the result.

To release, after the PR is merged into `main` with a merge commit:

```sh
git tag -a vX.Y.Z -m vX.Y.Z <merge commit> && git push origin vX.Y.Z
gh release create vX.Y.Z --repo app-product-foundation/agent-ci --verify-tag --notes-file <notes>
```

CI on the tag runs `scripts/action-ref.sh check vX.Y.Z`, which also requires the action ref's
comment and `CHANGELOG.md` to name the tag.

## Development

```sh
python3 -m unittest discover -s tests          # render-prompt tests and snapshots
UPDATE_SNAPSHOTS=1 python3 -m unittest discover -s tests   # after an intended prompt change
scripts/action-ref.sh check
actionlint && shellcheck action/claude-review/scripts/*.sh scripts/*.sh && zizmor .
```

[`ci.yml`](.github/workflows/ci.yml) runs the same checks on GitHub-hosted runners, and
[`dogfood-review.yml`](.github/workflows/dogfood-review.yml) reviews this repository's own pull
requests with the reusable workflow from the PR, with `merge-verdict: true`.

Decisions are recorded in [`docs/adr/`](docs/adr/).
