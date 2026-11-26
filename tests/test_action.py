"""Tests for the tool restrictions in action/claude-review/action.yml.

Run from the repository root: python3 -m unittest discover -s tests
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTION = ROOT / "action/claude-review/action.yml"


def claude_args():
    """Return the folded `claude_args: >-` block of the claude-code-action step as one line."""
    lines = ACTION.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "claude_args: >-")
    indent = len(lines[start]) - len(lines[start].lstrip())
    block = []
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line.strip())
    return " ".join(part for part in block if part)


def flag_values(args, flag):
    return re.findall(rf'{re.escape(flag)} "([^"]*)"', args)


class ToolRestrictionTest(unittest.TestCase):
    def denied(self):
        return [
            rule.strip()
            for value in flag_values(claude_args(), "--disallowedTools")
            for rule in value.split(",")
        ]

    def test_git_directory_is_denied(self):
        # claude-code-action writes github_token into .git/config; the review must not read it.
        self.assertIn("Read(./.git/**)", self.denied())

    def test_proc_is_denied(self):
        # Process environments under /proc hold the job's tokens.
        self.assertIn("Read(//proc/**)", self.denied())

    def test_allowed_tools_are_read_only(self):
        # No tool that writes: a tool that posts could send any file Claude can read. The action's
        # post step posts the comment instead.
        allowed = flag_values(claude_args(), "--allowedTools")
        self.assertEqual(len(allowed), 1)
        self.assertEqual(
            allowed[0].split(","),
            [
                "Read",
                "Grep",
                "Glob",
                "Bash(gh pr diff:*)",
                "Bash(gh pr view:*)",
                "Bash(gh issue view:*)",
            ],
        )

    def test_checkout_settings_are_not_loaded(self):
        self.assertIn("--setting-sources user", claude_args())

    def test_error_step_does_not_print_a_withheld_reply(self):
        text = ACTION.read_text(encoding="utf-8")
        step = text[text.index("- name: Show the Claude error"):]
        self.assertIn("if: failure() && steps.claude.outcome == 'failure'", step.split("\n")[1])

    def test_comment_is_posted_after_claude(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertLess(text.index("id: claude"), text.index("- name: Post the review comment"))
        self.assertIn("scripts/post-comment.py", text)


if __name__ == "__main__":
    unittest.main()
