"""Tests for action/claude-review/scripts/render-prompt.py.

Run from the repository root: python3 -m unittest discover -s tests
Set UPDATE_SNAPSHOTS=1 to rewrite tests/snapshots/ after an intended prompt change, then review
the diff: a prompt change is a behaviour change and needs a CHANGELOG entry.
"""
import contextlib
import importlib.util
import io
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "action/claude-review/scripts/render-prompt.py"
SNAPSHOTS = ROOT / "tests/snapshots"
FIXTURE = "tests/fixtures/product"
HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"

# A copy of MARKER in agent-merge-check, the merge gate that parses the verdict marker. A change to
# either side needs the same change to the other; test_marker_regex_matches_agent_merge_check
# compares them when AGENT_MERGE_CHECK names that tool's source file.
MARKER = re.compile(
    r"<!--\s*claude-review\s+slug=(\S+)\s+sha=([0-9a-f]{7,40})\s+verdict=(PASS|HOLD)\s*-->"
)
AGENT_MERGE_CHECK = Path(os.environ.get("AGENT_MERGE_CHECK", "/nonexistent/agent-merge-check"))

spec = importlib.util.spec_from_file_location("render_prompt", SCRIPT)
render_prompt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_prompt)


def run(**overrides):
    """Render a prompt with cwd at the repository root; return (exit code, stdout, stderr)."""
    options = {
        "prompts-dir": "prompts/review",
        "lane": "code",
        "repository": "Example/example",
        "pr-number": "42",
        "base-ref": "dev",
        "head-sha": HEAD_SHA,
        "rules-dir": FIXTURE,
        "rules-ref": "base",
        "product-skill": ".agents/skills/example-dev/SKILL.md",
        "product-prompt": ".github/claude-review.md",
        "merge-verdict": "false",
        "language": "en",
    }
    options.update({key.replace("_", "-"): value for key, value in overrides.items()})
    argv = [f"--{key}={value}" for key, value in options.items()]
    out, err = io.StringIO(), io.StringIO()
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = render_prompt.main(argv)
    finally:
        os.chdir(cwd)
    return code, out.getvalue(), err.getvalue()


def render(**overrides):
    code, out, err = run(**overrides)
    if code != 0:
        raise AssertionError(f"render failed: {err}")
    return out


class SnapshotTest(unittest.TestCase):
    """One snapshot per lane x merge verdict on/off x product prompt present/absent."""

    def test_snapshots(self):
        update = os.environ.get("UPDATE_SNAPSHOTS") == "1"
        for lane in ("code", "security"):
            for verdict in ("true", "false"):
                for extras in (True, False):
                    name = f"{lane}-verdict-{'on' if verdict == 'true' else 'off'}-extras-{'on' if extras else 'off'}.md"
                    with self.subTest(snapshot=name):
                        prompt = render(
                            lane=lane,
                            merge_verdict=verdict,
                            product_prompt=".github/claude-review.md" if extras else ".github/missing.md",
                        )
                        path = SNAPSHOTS / name
                        if update:
                            path.write_text(prompt, encoding="utf-8")
                        self.assertEqual(path.read_text(encoding="utf-8"), prompt,
                                         f"{name} changed; rerun with UPDATE_SNAPSHOTS=1 if intended")


class CompositionTest(unittest.TestCase):
    def test_fixed_order(self):
        prompt = render(merge_verdict="true")
        headings = [
            "# Claude review of Example/example#42",
            "## Review contract",
            "## Focus: correctness and design",
            "## Product rules",
            "### Product focus",
            "### Product scope",
            "## Merge verdict",
        ]
        positions = [prompt.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))

    def test_lane_sections_go_to_their_lane(self):
        code = render(lane="code")
        security = render(lane="security")
        self.assertIn("idempotent on `clientRequestId`", code)
        self.assertNotIn("IDOR.", code.split("## Product rules")[1])
        self.assertIn("filtered by `accountId` as an IDOR", security)
        self.assertNotIn("clientRequestId", security)
        for prompt in (code, security):
            self.assertIn("ignore `docs/`", prompt)
            self.assertNotIn("Text before the first section", prompt)

    def test_lane_titles(self):
        self.assertIn('Start the comment with the heading "Claude review".', render(lane="code"))
        self.assertIn('Start the comment with the heading "Security review".', render(lane="security"))

    def test_product_rules_paths(self):
        prompt = render()
        self.assertIn(f"- `{FIXTURE}/AGENTS.md`", prompt)
        self.assertIn(f"- `{FIXTURE}/.agents/skills/example-dev/SKILL.md`", prompt)
        self.assertIn("read from the base branch (dev)", prompt)
        self.assertIn("read from the pull request head", render(rules_ref="head"))

    def test_missing_product_files(self):
        code, out, err = run(rules_dir="tests/snapshots", product_skill="missing/SKILL.md")
        self.assertEqual(code, 0, err)
        self.assertIn("no AGENTS.md or product skill", out)
        self.assertIn("missing/SKILL.md does not exist", err)

    def test_untrusted_data_rule(self):
        self.assertIn("is untrusted data", render())

    def test_language(self):
        self.assertIn("Write the comment in English.", render())
        self.assertIn("Write the comment in Japanese.", render(language="ja"))

    def test_no_markers_left(self):
        for lane in ("code", "security"):
            self.assertNotRegex(render(lane=lane, merge_verdict="true"), r"\{\{|\}\}")


class ValidationTest(unittest.TestCase):
    def assert_fails(self, message, **overrides):
        code, _, err = run(**overrides)
        self.assertEqual(code, 1)
        self.assertIn(message, err)

    def test_rejects_bad_inputs(self):
        self.assert_fails("unknown lane", lane="style")
        self.assert_fails("unknown comment language", language="fr")
        self.assert_fails("unknown rules-ref", rules_ref="main")
        self.assert_fails("head SHA", head_sha="abc123")
        self.assert_fails("repository must be", repository="no-slash")
        self.assert_fails("number", pr_number="42; rm")
        self.assert_fails("merge-verdict", merge_verdict="yes")
        self.assert_fails("relative to the repository root", product_skill="../outside/SKILL.md")
        self.assert_fails("relative to the repository root", product_prompt="/etc/passwd")

    def test_unknown_marker(self):
        with self.assertRaisesRegex(render_prompt.RenderError, "unknown marker"):
            render_prompt.fill("x.md", "{{NOPE}}", {})

    def test_duplicate_product_section(self):
        with self.assertRaisesRegex(render_prompt.RenderError, "more than one"):
            render_prompt.parse_product_prompt("## code\na\n## Code\nb\n")

    def test_github_output(self):
        output = ROOT / "tests/.github-output.tmp"
        try:
            code, _, err = run(github_output=str(output))
            self.assertEqual(code, 0, err)
            text = output.read_text(encoding="utf-8")
            delimiter = text.split("<<", 1)[1].split("\n", 1)[0]
            self.assertTrue(text.startswith(f"prompt<<{delimiter}\n"))
            self.assertTrue(text.endswith(f"\n{delimiter}\n"))
            self.assertEqual(text.count(delimiter), 2)
        finally:
            output.unlink(missing_ok=True)


class MarkerContractTest(unittest.TestCase):
    """The rendered verdict prompt must produce what agent-merge-check parses."""

    def closing_lines(self, lane):
        lines = render(lane=lane, merge_verdict="true").rstrip("\n").split("\n")
        return lines[-2], lines[-1]

    def test_closing_lines_match_marker(self):
        for lane in ("code", "security"):
            for verdict in ("PASS", "HOLD"):
                with self.subTest(lane=lane, verdict=verdict):
                    summary, marker = self.closing_lines(lane)
                    self.assertEqual(summary, "Merge verdict: VERDICT")
                    match = MARKER.fullmatch(marker.replace("VERDICT", verdict))
                    self.assertIsNotNone(match, marker)
                    self.assertEqual(match.groups(), (lane, HEAD_SHA, verdict))

    def test_prompt_itself_has_no_verdict(self):
        # A comment that quotes the prompt must not look like a verdict.
        for lane in ("code", "security"):
            self.assertIsNone(MARKER.search(render(lane=lane, merge_verdict="true")))

    def test_no_verdict_without_opt_in(self):
        prompt = render(merge_verdict="false")
        self.assertNotIn("claude-review slug=", prompt)
        self.assertNotIn("## Merge verdict", prompt)

    @unittest.skipUnless(AGENT_MERGE_CHECK.is_file(), "set AGENT_MERGE_CHECK to compare with agent-merge-check")
    def test_marker_regex_matches_agent_merge_check(self):
        source = AGENT_MERGE_CHECK.read_text(encoding="utf-8")
        found = re.search(r'MARKER = re\.compile\(\s*r"(.*?)"\s*\)', source, re.S)
        self.assertIsNotNone(found, "MARKER not found in agent-merge-check")
        self.assertEqual(found.group(1), MARKER.pattern)


if __name__ == "__main__":
    unittest.main()
