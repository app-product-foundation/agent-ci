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
    def test_git_directory_is_denied(self):
        # claude-code-action writes github_token into .git/config; the review must not read it.
        denied = [
            rule.strip()
            for value in flag_values(claude_args(), "--disallowedTools")
            for rule in value.split(",")
        ]
        self.assertIn("Read(./.git/**)", denied)

    def test_allowed_tools_are_read_only(self):
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
                "Bash(gh pr comment:*)",
                "Bash(gh issue view:*)",
            ],
        )

    def test_checkout_settings_are_not_loaded(self):
        self.assertIn("--setting-sources user", claude_args())


if __name__ == "__main__":
    unittest.main()
