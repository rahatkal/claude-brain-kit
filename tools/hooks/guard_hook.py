"""Session guardrails.

  SessionStart:  python guard_hook.py start  -> injects the PLAYBOOK corrections log + insights.md as context
  PreToolUse:    python guard_hook.py pre    -> denies .env reads, commands in DANGER and git push
  Stop:          python guard_hook.py stop   -> uncommitted vault changes: sends Claude back once to log + commit

Enforces in code what AGENTS.md only says in text. You run the blocked actions yourself.
Edit DANGER below to block your own risky commands (deploys, prod DB, payments...).
Never touches the network; any error fails open (exit 0, no output) so a bug can't brick a session.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = re.compile(r"(^|[\\/\s\"'=])\.env(?![.\w-]*(example|sample|template))(\.[\w-]+)?(?=$|[\s\"'/\\;|&)])", re.I)
DANGER = re.compile(
    r"\brm\s+-rf\s+[/~]"           # wipe root/home
    r"|\bDROP\s+(TABLE|DATABASE)\b"  # drop a database
    r"|--force\b.*\bprod",           # forced prod actions
    re.I,
)
GIT_PUSH = re.compile(r"\bgit(\s+-[cC]\s+\S+|\s+--?[\w-]+(=\S+)?)*\s+push\b", re.I)  # push as the subcommand only


def section(text, heading):
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.S | re.M | re.I)
    return m.group(1).strip() if m else ""


def start():
    parts = []
    pb = ROOT / "night-shift" / "PLAYBOOK.md"
    if pb.exists():
        log = section(pb.read_text(encoding="utf-8"), "Corrections log")
        log = "\n".join(l for l in log.splitlines() if not l.strip().startswith("<!--"))
        if log:
            parts.append("PLAYBOOK corrections log (the owner's rules, follow them):\n" + log)
    ins = ROOT / "night-shift" / "insights.md"
    if ins.exists():
        t = ins.read_text(encoding="utf-8")
        body = "\n".join(s for s in (section(t, "Insights"), section(t, "Proven routines")) if s)
        body = "\n".join(l for l in body.splitlines() if l.strip() and not l.strip().startswith("<!--"))
        parts.append("insights.md (candidates, not rules):\n" + (body or "(none yet)"))
    if parts:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                 "additionalContext": "\n\n".join(parts)}}))


FIRES = ROOT / "night-shift" / "rule-fires.csv"  # date,hook,rule — /review counts these to prune rules that never fire


def log_fire(hook, rule):
    import datetime
    new = not FIRES.exists()
    with FIRES.open("a", encoding="utf-8") as f:
        if new:
            f.write("date,hook,rule\n")
        f.write(f"{datetime.date.today():%Y-%m-%d},{hook},{rule.replace(',', ';')}\n")


def deny(reason):
    try:
        log_fire("guard_hook.pre", reason)
    except Exception:
        pass
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason + " (tools/hooks/guard_hook.py). Ask the user to do this themselves."}}))


def pre():
    d = json.load(sys.stdin)
    tool, inp = d.get("tool_name", ""), d.get("tool_input") or {}
    if tool in ("Bash", "PowerShell"):
        cmd = inp.get("command", "")
        if GIT_PUSH.search(cmd):
            return deny("git push is blocked")
        if DANGER.search(cmd):
            return deny("Command matches the DANGER list")
        if ENV_FILE.search(cmd) and "grep -v PRIVATE_KEY" not in cmd:
            return deny(".env access blocked; inspect it only with grep -v PRIVATE_KEY")
    else:
        path = inp.get("file_path") or inp.get("path") or inp.get("notebook_path") or ""
        if ENV_FILE.search(path) or (tool == "Grep" and ENV_FILE.search(inp.get("glob", ""))):
            return deny(".env files are never read or edited")


# files rewritten automatically every session; never count as "work left uncommitted"
AUTO_FILES = {"night-shift/rule-fires.csv"}


def stop():
    import datetime, subprocess
    d = json.load(sys.stdin)
    if d.get("stop_hook_active"):  # already sent back once this stop; never loop
        return
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, timeout=8).stdout
    dirty = []
    for l in out.splitlines():
        f = l[3:].strip().strip('"')
        if f in AUTO_FILES:
            continue
        if l.startswith("??") and f.startswith(".drafts/"):  # unverified drafts, maybe another session's work in progress
            continue
        dirty.append(f)
    if not dirty:
        return
    log = f"night-shift/log/{datetime.date.today():%Y-%m-%d}.md"
    shown = ", ".join(dirty[:5]) + (f" (+{len(dirty) - 5} more)" if len(dirty) > 5 else "")
    print(json.dumps({"decision": "block", "reason":
        f"Uncommitted vault changes: {shown}. Per AGENTS.md, before ending: append 3-6 fact lines to {log} "
        f"(what changed, verifier FAILs, the user's corrections), then `git add -A && git commit`. "
        f"If you are mid-task or waiting on the user's answer, say so in one line and stop instead."}))


if __name__ == "__main__":
    try:
        {"start": start, "pre": pre, "stop": stop}[sys.argv[1]]()
    except Exception:
        pass
