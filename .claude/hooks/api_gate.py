"""Owner's rule: no session may call the Meta Model API unless the owner's message contains the word GO in capitals.

Where .claude/require_go exists (the owner's machine only; git-ignored), relight/models.py refuses every live request
unless .claude/api_go exists or the owner set RELIGHT_ALLOW_API=1 in their own shell. This hook, wired in the
git-ignored .claude/settings.local.json, is the only thing that creates api_go, and only from the owner's message:

  prompt  (UserPromptSubmit): GO in the message -> open the gate for this turn; otherwise close it
  stop    (Stop)            : the turn is over -> close it
  start   (SessionStart)    : a new session starts closed
  guard   (PreToolUse)      : refuse tool calls that would open the gate, lift the restriction, or touch .env (where
                              the API key lives: it must never be read into a session or committed)

Exit code 2 with a message on stderr blocks a tool call.
"""

import json
import re
import sys
import time
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / "api_go"
GO = re.compile(r"(?<![A-Za-z])GO(?![A-Za-z])")


def close() -> None:
    GATE.unlink(missing_ok=True)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        data = {}
    if mode == "prompt":
        if GO.search(data.get("prompt") or ""):
            GATE.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext":
                  "The owner wrote GO: Meta Model API calls are allowed for this turn only."}}))
        else:
            close()
    elif mode in ("stop", "start"):
        close()
    elif mode == "guard":
        tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
        shell = tool in ("Bash", "PowerShell")
        text = json.dumps(inp) if shell else str(inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or "")
        if re.search(r"api_go|require_go|RELIGHT_ALLOW_API", text):
            print("Blocked: only the owner can allow Meta Model API calls, by writing GO in a message.", file=sys.stderr)
            sys.exit(2)
        # .env holds the API key. .env.example (no key) stays editable.
        env = r"\.env(?![\w.])" if shell else r"(^|[\\/])\.env$"
        if re.search(env, text):
            print("Blocked: .env holds the API key; sessions never read, write or commit it. The owner edits it by hand.",
                  file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
