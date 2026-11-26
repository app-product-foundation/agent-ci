"""Tests for action/claude-review/scripts/post-comment.py.

Run from the repository root: python3 -m unittest discover -s tests
"""
import base64
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "action/claude-review/scripts/post-comment.py"

spec = importlib.util.spec_from_file_location("post_comment", SCRIPT)
post_comment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post_comment)

# Made-up values in the shape of the real secrets.
GH_TOKEN = "ghs_" + "A1b2C3d4E5" * 4
OAUTH_TOKEN = "sk-ant-oat01-" + "x9Y8z7W6v5" * 5
ENV = {"GH_TOKEN": GH_TOKEN, "CLAUDE_CODE_OAUTH_TOKEN": OAUTH_TOKEN}


class PostCommentTest(unittest.TestCase):
    def run_script(self, messages, environ=ENV, pr_number="42"):
        posted = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "execution.json"
            if messages is not None:
                path.write_text(json.dumps(messages), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = post_comment.main(
                    [
                        "--execution-file", str(path),
                        "--repository", "Example/example",
                        "--pr-number", pr_number,
                        "--lane", "code",
                    ],
                    poster=lambda repo, pr, body: posted.append((repo, pr, body)),
                    environ=environ,
                )
        return code, posted, out.getvalue()

    @staticmethod
    def reply(text, subtype="success"):
        return [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "thinking"}]}},
            {"type": "result", "subtype": subtype, "is_error": False, "result": text},
        ]

    def assert_withheld(self, text):
        code, posted, out = self.run_script(self.reply(text))
        self.assertEqual(code, 1)
        self.assertEqual(len(posted), 1)
        body = posted[0][2]
        self.assertIn("was not posted", body)
        self.assertNotIn("claude-review slug=", body)
        for secret in ENV.values():
            self.assertNotIn(secret, body)
            self.assertNotIn(secret, out)
        return body

    def test_posts_the_final_reply(self):
        text = "Claude review\n\nNo findings.\n\n<!-- claude-review slug=code sha=abc1234 verdict=PASS -->"
        code, posted, _ = self.run_script(self.reply(text))
        self.assertEqual(code, 0)
        self.assertEqual(posted, [("Example/example", "42", text + "\n")])

    def test_withholds_each_token(self):
        for secret in ENV.values():
            with self.subTest(secret=secret[:6]):
                self.assert_withheld(f"Claude review\n\nThe value is {secret}.")

    def test_withholds_base64_of_a_token(self):
        for prefix in ("", "a", "ab"):
            encoded = base64.b64encode(f"{prefix}token={GH_TOKEN}\n".encode()).decode()
            with self.subTest(prefix=prefix):
                self.assert_withheld(f"Claude review\n\n{encoded}")

    def test_withholds_credential_shapes(self):
        for text in (
            "url = https://x-access-token:unknownsecret1@github.com/a/b.git",
            "token ghp_" + "Q" * 36,
            "key sk-ant-api03-" + "k" * 30,
        ):
            with self.subTest(text=text[:20]):
                self.assert_withheld(text)

    def test_ordinary_review_text_is_not_withheld(self):
        text = (
            "Claude review\n\n- `src/a.ts:10` uses https://example.com/docs and `user@example.com`.\n"
            "- A short value like `ghs_` or `sk-ant-` alone is fine.\n"
        )
        code, posted, _ = self.run_script(self.reply(text))
        self.assertEqual(code, 0)
        self.assertEqual(posted[0][2], text)

    def test_nothing_posted_without_a_finished_reply(self):
        for messages in (
            None,
            [],
            self.reply(""),
            self.reply("   \n"),
            self.reply("partial", subtype="error_max_turns"),
        ):
            with self.subTest(messages=messages):
                code, posted, _ = self.run_script(messages)
                self.assertEqual(code, 1)
                self.assertEqual(posted, [])

    def test_too_long_reply_is_withheld(self):
        code, posted, _ = self.run_script(self.reply("x" * (post_comment.MAX_BODY + 1)))
        self.assertEqual(code, 1)
        self.assertIn("too long", posted[0][2])

    def test_rejects_bad_pr_number(self):
        code, posted, _ = self.run_script(self.reply("ok"), pr_number="1 --repo other/repo")
        self.assertEqual(code, 1)
        self.assertEqual(posted, [])


if __name__ == "__main__":
    unittest.main()
