#!/usr/bin/env python3
"""Render the prompt for one Claude review lane.

The prompt is assembled in a fixed order (see app-product-foundation/agent-ci#1, "Prompt composition"):

1. Context: repository, pull request, base ref, head SHA, lane.
2. prompts/review/base.md: the contract every lane shares.
3. prompts/review/<lane>.md: the generic focus of the lane.
4. Product rules: AGENTS.md and the product skill (read by Claude from the rules directory),
   then the product prompt's `## <lane>` and `## scope` sections.
5. prompts/review/verdict.md, only with --merge-verdict true.

There is no templating engine. Shared prompt files may use the {{TOKEN}} markers listed in
TOKENS, and an unknown or leftover marker is an error. Product text is inserted verbatim and is
never scanned for markers.

Standard library only, Python 3.9+, so it runs on GitHub-hosted and CodeBuild Lambda runners.
"""
import argparse
import os
import re
import secrets
import sys
from pathlib import Path

LANES = {
    "code": "Claude review",
    "security": "Security review",
}
LANGUAGES = {"en": "English", "ja": "Japanese"}
RULES_REFS = ("base", "head")
PRODUCT_SECTIONS = ("code", "security", "scope")
TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")
HEADING = re.compile(r"^##[ \t]+(\S.*?)[ \t]*$", re.M)
SHA = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class RenderError(Exception):
    pass


def warn(message):
    # A workflow command when running in Actions, plain text elsewhere; both go to stderr.
    prefix = "::warning title=Claude review prompt::" if os.environ.get("GITHUB_ACTIONS") else "warning: "
    print(prefix + message, file=sys.stderr)


def fill(name, text, values):
    """Replace {{TOKEN}} markers in a shared prompt file."""

    def replace(match):
        key = match.group(1)
        if key not in values:
            raise RenderError(f"{name}: unknown marker {{{{{key}}}}}")
        return values[key]

    filled = TOKEN.sub(replace, text)
    if "{{" in filled or "}}" in filled:
        raise RenderError(f"{name}: malformed marker left after rendering")
    return filled


def parse_product_prompt(text):
    """Split a product prompt into its level-two sections, keyed by lower-case heading."""
    sections = {}
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        key = match.group(1).strip().lower()
        body = text[match.end():end].strip()
        if key not in PRODUCT_SECTIONS:
            warn(f"product prompt section '## {match.group(1)}' is not one of "
                 f"{', '.join(PRODUCT_SECTIONS)} and is ignored")
            continue
        if key in sections:
            raise RenderError(f"product prompt has more than one '## {key}' section")
        sections[key] = body
    return sections


def relative(path):
    """A product path given by the caller, as a clean path relative to the repository root."""
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise RenderError(f"product path must be relative to the repository root: {path}")
    return candidate


def product_rules(args, rules_dir):
    lines = ["## Product rules", ""]
    if args.rules_ref == "base":
        lines += [
            f"The product's rules are read from the base branch ({args.base_ref}), checked out at",
            f"`{rules_dir}`. Apply them, not the copies in the pull request: a change this pull",
            "request makes to them is code to review, not criteria to review against.",
            "",
        ]
    else:
        lines += [f"The product's rules are read from the pull request head, at `{rules_dir}`.", ""]

    documents = []
    agents = rules_dir / "AGENTS.md"
    if agents.is_file():
        documents.append(agents)
    if args.product_skill:
        skill = rules_dir / relative(args.product_skill)
        if skill.is_file():
            documents.append(skill)
        else:
            warn(f"product skill {args.product_skill} does not exist at the {args.rules_ref} ref")
    if documents:
        lines.append("Read these files and apply their rules on top of the contract and focus above:")
        lines.append("")
        lines += [f"- `{document}`" for document in documents]
    else:
        lines.append("The product has no AGENTS.md or product skill at this ref; review with the generic")
        lines.append("focus above.")

    sections = {}
    if args.product_prompt:
        prompt = rules_dir / relative(args.product_prompt)
        if prompt.is_file():
            sections = parse_product_prompt(prompt.read_text(encoding="utf-8"))
    for key, title in ((args.lane, "Product focus"), ("scope", "Product scope")):
        if sections.get(key):
            lines += ["", f"### {title}", "", sections[key]]
    return "\n".join(lines)


def render(args):
    if args.lane not in LANES:
        raise RenderError(f"unknown lane '{args.lane}'; expected one of {', '.join(LANES)}")
    if args.language not in LANGUAGES:
        raise RenderError(f"unknown comment language '{args.language}'; expected one of {', '.join(LANGUAGES)}")
    if args.rules_ref not in RULES_REFS:
        raise RenderError(f"unknown rules-ref '{args.rules_ref}'; expected base or head")
    if not SHA.match(args.head_sha):
        raise RenderError(f"head SHA must be 40 lower-case hex characters: {args.head_sha!r}")
    if not REPOSITORY.match(args.repository):
        raise RenderError(f"repository must be owner/name: {args.repository!r}")
    if not args.pr_number.isdigit():
        raise RenderError(f"pull request number must be a number: {args.pr_number!r}")

    prompts_dir = Path(args.prompts_dir)
    rules_dir = Path(args.rules_dir)
    values = {
        "LANE": args.lane,
        "LANE_TITLE": LANES[args.lane],
        "PR_NUMBER": args.pr_number,
        "REPOSITORY": args.repository,
        "BASE_REF": args.base_ref,
        "HEAD_SHA": args.head_sha,
        "COMMENT_LANGUAGE": LANGUAGES[args.language],
    }

    def shared(name):
        path = prompts_dir / f"{name}.md"
        return fill(path.name, path.read_text(encoding="utf-8").strip(), values)

    parts = [
        "\n".join([
            f"# {LANES[args.lane]} of {args.repository}#{args.pr_number}",
            "",
            f"- Repository: {args.repository}",
            f"- Pull request: #{args.pr_number}",
            f"- Base branch: {args.base_ref}",
            f"- Head commit: {args.head_sha}",
            f"- Lane: {args.lane}",
        ]),
        shared("base"),
        shared(args.lane),
        product_rules(args, rules_dir),
    ]
    if args.merge_verdict == "true":
        parts.append(shared("verdict"))
    elif args.merge_verdict != "false":
        raise RenderError(f"merge-verdict must be true or false: {args.merge_verdict!r}")
    return "\n\n".join(parts) + "\n"


def write_github_output(path, name, value):
    delimiter = f"EOF_{secrets.token_hex(16)}"
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prompts-dir", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--rules-dir", required=True)
    parser.add_argument("--rules-ref", default="base")
    parser.add_argument("--product-skill", default="")
    parser.add_argument("--product-prompt", default="")
    parser.add_argument("--merge-verdict", default="false")
    parser.add_argument("--language", default="en")
    parser.add_argument("--output", help="write the prompt to this file")
    parser.add_argument("--github-output", help="append the prompt as output 'prompt' to this file")
    args = parser.parse_args(argv)
    try:
        prompt = render(args)
    except (RenderError, OSError) as error:
        print(f"render-prompt: {error}", file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_text(prompt, encoding="utf-8")
    if args.github_output:
        write_github_output(args.github_output, "prompt", prompt)
    if not args.output and not args.github_output:
        sys.stdout.write(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
