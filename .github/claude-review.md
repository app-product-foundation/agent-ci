# Claude review extras for agent-ci

## code

This repository is the shared review skeleton that other repositories pin. Check that:

- The marker line in `prompts/review/verdict.md` still matches the `MARKER` regex in
  `tests/test_render_prompt.py`, and both stay equal to the one in `agent-merge-check`.
- Inputs, check names (`Claude review`, `Claude security review`) and the marker are not changed
  without a major version bump in `CHANGELOG.md`.
- A prompt change updates `tests/snapshots/` and has a `CHANGELOG.md` entry that says the review
  output changes.

## security

Callers pass `CLAUDE_CODE_OAUTH_TOKEN` and grant `pull-requests: write`. Treat any change that lets
pull request content reach a shell, widens Claude's allowed tools beyond read-only `gh` and file
reads, or loosens the author, draft or same-repository gate as a vulnerability.

## scope

`tests/fixtures/` and `tests/snapshots/` are test data; review them only for consistency with the
prompts.
