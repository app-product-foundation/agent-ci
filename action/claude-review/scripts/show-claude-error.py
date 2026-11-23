#!/usr/bin/env python3
"""Print the error text of Claude's final result message.

claude-code-action hides Claude's output, so a failed run (a rejected token, a usage limit) shows
no cause. This prints only the final result message's text and subtype, never the full
transcript, which can contain file contents.

Usage: show-claude-error.py <execution-file>
"""
import json
import sys


def main(argv):
    path = argv[1] if len(argv) > 1 else ""
    try:
        with open(path, encoding="utf-8") as handle:
            messages = json.load(handle)
    except FileNotFoundError:
        print("No Claude execution output; the action failed before Claude ran.")
        return 0
    except (OSError, ValueError) as error:
        print(f"Could not read the Claude execution output: {error}")
        return 0
    results = [m for m in messages if isinstance(m, dict) and m.get("type") == "result"]
    last = results[-1] if results else {}
    print(f"Claude error: {last.get('result') or 'no result text'} (subtype: {last.get('subtype') or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
