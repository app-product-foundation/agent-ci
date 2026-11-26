#!/usr/bin/env python3
"""Post Claude's final reply as the lane's pull request comment.

Claude has no write tools: it gives the review comment as its final reply, and this step posts it
with the action's token. Before posting, the reply is checked for the secrets this job holds and for
credential-shaped strings. A reply that fails the check is not posted; a fixed notice is posted in
its place, so the lane still leaves one comment and no merge verdict, and the step fails.

This check is a second layer. The first is that Claude cannot read the secrets: the action denies
its file tools under .git/ and /proc/, and its only shell commands are read-only gh subcommands.

Usage: post-comment.py --execution-file <file> --repository <owner/repo> --pr-number <n> --lane <lane>
Secrets to look for are read from the environment variables named in SECRET_ENV. GH_TOKEN is the
token gh posts with.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys

SECRET_ENV = ("GH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")
# Credential shapes, whoever they belong to: GitHub tokens, Anthropic keys and OAuth tokens, and a
# credential embedded in a URL (https://user:secret@host).
CREDENTIAL_PATTERNS = (
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b[a-z][a-z0-9+.-]{0,30}://[^/\s:@]+:[^/\s@]{8,}@", re.IGNORECASE),
)
# GitHub rejects longer comment bodies.
MAX_BODY = 65536


class PostError(Exception):
    pass


def final_reply(path):
    """Return the text of Claude's last result message, or raise PostError."""
    try:
        with open(path, encoding="utf-8") as handle:
            messages = json.load(handle)
    except (OSError, ValueError) as error:
        raise PostError(f"cannot read the Claude execution output: {error}") from error
    results = [m for m in messages if isinstance(m, dict) and m.get("type") == "result"]
    if not results:
        raise PostError("the Claude execution output has no result message")
    last = results[-1]
    text = last.get("result")
    if last.get("subtype") != "success" or last.get("is_error"):
        raise PostError(f"Claude did not finish (subtype: {last.get('subtype') or 'none'})")
    if not isinstance(text, str) or not text.strip():
        raise PostError("Claude's final reply is empty")
    return text.strip() + "\n"


def secret_forms(value):
    """The secret as written, and base64-encoded at each of the three byte alignments."""
    forms = {value}
    raw = value.encode()
    for offset in range(3):
        encoded = base64.b64encode(b"\0" * offset + raw).decode()
        # Drop the characters that depend on the padding bytes or on what follows the secret.
        start = (offset * 4 + 2) // 3
        forms.add(encoded[start:-4] if len(encoded) - start > 8 else encoded)
    return {form for form in forms if len(form) >= 8}


def leaks(text, secrets):
    """Return why the text must not be posted, or None."""
    for name, value in secrets.items():
        if any(form in text for form in secret_forms(value)):
            return f"it contains the value of {name}"
    for pattern in CREDENTIAL_PATTERNS:
        if pattern.search(text):
            return "it contains a credential-shaped string"
    return None


def withheld_notice(lane, reason):
    return (
        f"Claude review lane `{lane}`: the review was not posted because {reason}.\n\n"
        "No merge verdict is given. See the workflow run for details.\n"
    )


def post(repository, pr_number, body):
    subprocess.run(
        ["gh", "pr", "comment", pr_number, "--repo", repository, "--body-file", "-"],
        input=body,
        text=True,
        check=True,
    )


def main(argv=None, poster=post, environ=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--execution-file", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--lane", required=True)
    args = parser.parse_args(argv)
    environ = os.environ if environ is None else environ
    if not re.fullmatch(r"[1-9][0-9]*", args.pr_number):
        print(f"::error title=Claude review::bad pull request number '{args.pr_number}'")
        return 1
    try:
        body = final_reply(args.execution_file)
    except PostError as error:
        print(f"::error title=Claude review::{error}; no comment posted")
        return 1
    secrets = {name: environ[name] for name in SECRET_ENV if environ.get(name)}
    reason = leaks(body, secrets)
    if reason:
        print(f"::error title=Claude review::the reply was withheld because {reason}")
        poster(args.repository, args.pr_number, withheld_notice(args.lane, reason))
        return 1
    if len(body) > MAX_BODY:
        print(f"::error title=Claude review::the reply is {len(body)} characters; GitHub allows {MAX_BODY}")
        poster(args.repository, args.pr_number, withheld_notice(args.lane, "it is too long for a comment"))
        return 1
    poster(args.repository, args.pr_number, body)
    print(f"Posted the {args.lane} review comment ({len(body)} characters).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
