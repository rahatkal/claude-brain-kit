"""Session guardrails.

  SessionStart:  python guard_hook.py start  -> injects the PLAYBOOK corrections log + insights.md as context
  PreToolUse:    python guard_hook.py pre    -> denies .env reads, commands in DANGER, git push, commit hook bypass
                                                (--no-verify, core.hooksPath) and writes to tools/hooks + .claude/settings*.json
  Stop:          python guard_hook.py stop   -> uncommitted vault changes: sends Claude back once to log + commit

Enforces in code what AGENTS.md only says in text. You run the blocked actions yourself.
Edit DANGER below (by hand: Claude can't edit this folder) to block your own risky commands (deploys, prod DB, payments...).
Never touches the network; any error fails open (exit 0, no output) so a bug can't brick a session.
"""
import json, re, sys  # tests: tools/hooks/test_guard_hook.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ENV_RAW = re.compile(r"(?:^|[\\/\s\"'=*])\.env([\w.*-]*)", re.I)  # .env plus any suffix: .env.prod.bak, .env*
SAFE_ENV_SUFFIX = re.compile(r"[.\w-]*(example|sample|template)$", re.I)  # only these templates are readable


def env_hit(text):
    return any(not SAFE_ENV_SUFFIX.fullmatch(m.group(1)) for m in ENV_RAW.finditer(text or ""))


DANGER = re.compile(
    r"\brm\s+-rf\s+[/~]"           # wipe root/home
    r"|\bDROP\s+(TABLE|DATABASE)\b"  # drop a database
    r"|--force\b.*\bprod",           # forced prod actions
    re.I,
)
_ARG = r"""(?:"[^"]*"|'[^']*'|\S+)"""
_GIT_GLOBAL = rf"(?:\s+(?:(?:-C|-c|--git-dir|--work-tree|--namespace|--super-prefix|--config-env|--exec-path)(?:\s+|=){_ARG}|-\S+))*"
GIT_PUSH = re.compile(
    rf"\bgit(?:\.exe)?['\"]?{_GIT_GLOBAL}\s+['\"]?push\b"     # push as the subcommand, after any global options
    r"|\bgit\b[^;|&\n]*-c\s*\S*=\S*push",     # alias trick: git -c alias.x=push x
    re.I,
)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}


def safe_env_grep(cmd):
    """True only for `grep -v PRIVATE_KEY <envfile>`, optionally piped into `grep -v [-i] <pattern>` or head/tail."""
    import shlex
    if re.search(r"[;&#`$<>\n\r]", cmd):
        return False
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars="|")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return False
    segs, cur = [], []
    for t in toks:
        if t == "|":
            segs.append(cur)
            cur = []
        else:
            cur.append(t)
    segs.append(cur)
    first = segs[0]
    if not (len(first) == 4 and first[:3] == ["grep", "-v", "PRIVATE_KEY"]
            and not first[3].startswith("-") and env_hit(first[3])):
        return False
    for s in segs[1:]:
        if s and s[0] == "grep":
            flags, args = [t for t in s[1:] if t.startswith("-")], [t for t in s[1:] if not t.startswith("-")]
            if not (len(args) == 1 and flags and set("".join(flags).lstrip("-").replace("-", "")) <= set("viE")
                    and "v" in "".join(flags) and not env_hit(args[0])):
                return False
        elif s and s[0] in ("head", "tail"):
            if not all(re.fullmatch(r"-n|-?\d+", t) for t in s[1:]):
                return False
        else:
            return False
    return True


def dir_has_env(path, cap=20000):
    """Recursive Grep on a dir would read any .env inside. Fails closed (True) past `cap` files."""
    import os
    n = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            n += 1
            if env_hit("/" + f) or n > cap:
                return True
    return False


def grep_reads_env(inp):
    import fnmatch, os
    glob, typ = inp.get("glob") or "", inp.get("type") or ""
    if "env" in glob.lower() or "env" in typ.lower():
        return True
    if typ or (glob and not fnmatch.fnmatch(".env", glob.split("/")[-1])):
        return False  # a file filter that cannot match .env
    path = inp.get("path") or os.getcwd()
    return os.path.isdir(path) and dir_has_env(path)


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


# --- commit hook bypass, and hooks/settings are owner-only ---------------------------------------------------
HF2 = "guard: git hook bypass blocked"
HF3 = "guard: hooks and settings are owner-only"
HOOK_NAMES = sorted(p.name.lower() for p in Path(__file__).parent.glob("*.py"))
CANON = ["tools/hooks", "tools/hooks/pre-commit", ".claude/settings.json", ".claude/settings.local.json",
         ".git/config", ".git/hooks"] + ["tools/hooks/" + n for n in HOOK_NAMES]
EDIT_PROT = re.compile(r"(?:^|/)(?:tools/hooks/|\.claude/settings(?:\.local)?\.json$|\.git/(?:config$|hooks/))")
_END = r"""(?=$|['"\s,);])"""
SHELL_PROT = re.compile(
    r"""(?:^|[/=:'"\s(,])(?:"""
    r"(?:tools/hooks|\.git/hooks)(?=$|[/'\"\s,);])"
    r"|(?:tools|hooks|\.claude|\.git)/?" + _END +
    r"|(?:\.claude/settings[\w.-]*|\.git/config|hooks/pre-commit|settings(?:\.local)?\.json|"
    + "|".join(re.escape(n) for n in HOOK_NAMES) + ")" + _END + ")")
SHELL_GATE = re.compile(r"hook|claude|\.git|settings|tools|[*?\[]", re.I)
READ_CMDS = {"cat", "type", "more", "less", "head", "tail", "grep", "egrep", "fgrep", "findstr", "wc", "diff", "cmp",
             "ls", "dir", "stat", "file", "md5sum", "sha256sum", "get-content", "gc", "select-string", "sls",
             "get-childitem", "gci", "get-item", "gi", "get-filehash", "test-path", "resolve-path", "echo",
             "write-output", "write-host", "where", "which"}
GIT_READ = {"status", "diff", "log", "show", "blame", "grep", "add", "commit", "ls-files", "ls-tree", "rev-parse",
            "cat-file", "shortlog", "check-ignore"}
OUT_OPT = re.compile(r"--?(?:o|out\w*|basetemp|junit-?xml\w*|result-?log)(?:=(.*))?$")
PYTEST_FLAG = re.compile(r"-(?:q+|v+|x|s|l|ra)$|--(?:lf|ff|co|sw|collect-only|no-header|tb=\w+)$")
GIT_ARG_OPTS = {"-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"}
# options whose value is free text (commit message, log filter): never scanned for flags
GIT_TEXT_OPTS = {"-m", "--message", "-F", "--file", "-C", "-c", "-t", "--template", "--author", "--date", "--grep",
                 "-S", "-G", "--format", "--pretty", "--fixup", "--squash", "--trailer", "--cleanup"}
CFG_READ_OPTS = {"--get", "--get-all", "--get-regexp", "--local", "--global", "--system", "--worktree",
                 "--show-origin", "--show-scope", "--includes", "--no-includes", "-z", "--null", "--bool", "--int",
                 "--path"}
HOOKS_KEY = re.compile(r"core\.hooks", re.I)
SELF_PROTECT = True  # False lets Claude edit tools/hooks, .claude/settings*.json and .git/config (not recommended)


def _norm(p):
    import posixpath
    p = p.strip().strip("'\"").replace("\\", "/").lower()
    return posixpath.normpath(p) if p else ""


def _base(word):
    import posixpath
    b = posixpath.basename(_norm(word))
    return b[:-4] if b.endswith(".exe") else b


def _glob_hit(n):
    import fnmatch
    parts = re.split(r"[=\s]", n)[-1].split("/")
    for c in CANON:
        cp = c.split("/")
        k = min(len(parts), len(cp))
        if all(fnmatch.fnmatchcase(a, b) for a, b in zip(cp[-k:], parts[-k:])):
            return True
    return False


def _prot(tok):
    n = _norm(tok)
    return bool(n) and bool(SHELL_PROT.search(n) or (re.search(r"[*?\[]", n) and _glob_hit(n)))


def _prep(cmd, ps):
    """Strip PowerShell escapes and `cat <<EOF` heredoc bodies (pure data, e.g. commit messages)."""
    if ps:
        cmd = cmd.replace("`", "")
    return re.sub(r"(\bcat\s+<<-?\s*(['\"]?)(\w+)\2)([^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|\)|$)", r"\1\4", cmd, flags=re.S)


def _subs(cmd):
    """Inner commands of $( ), <( ), >( ) and backticks: they run even inside a quoted argument."""
    return re.findall(r"[$<>]\(((?:[^()]|\([^()]*\))*)\)", cmd) + re.findall(r"`([^`]*)`", cmd)


def unshell(cmd, ps=False):
    """Shell unquoting, for matching only (bash reads .en''v, .e\\nv and .\\env as the secrets file). Returns
    (light, flat). light: escapes (bash \\x, PowerShell `x) and empty '' "" pairs dropped. flat: also every quote
    dropped, blanks collapsed. Each check denies if the raw text OR one of these matches."""
    light = cmd.replace("`", "") if ps else re.sub(r"\\([^\\\"'$`\n])", r"\1", cmd)
    light = re.sub(r"''|\"\"", "", light)
    if re.search(r"\bcmd(?:\.exe)?\b", cmd, re.I):  # cmd /c strips ^ escapes: .e^nv
        light = light.replace("^", "")
    return light, re.sub(r"[ \t]+", " ", re.sub(r"['\"]", "", light))


def shell_forms(cmd, ps=False):
    """(lights, flats): raw text plus unshell() forms; also the other shell's forms when it is invoked (bash -c ...)."""
    other = r"\b(?:ba|z|da|k)?sh\b|\bwsl\b" if ps else r"\b(?:powershell|pwsh)\b"
    forms = [unshell(cmd, ps)] + ([unshell(cmd, not ps)] if re.search(other, cmd, re.I) else [])
    return [cmd] + [f[0] for f in forms], [cmd] + [f[1] for f in forms]


SHELL_WRAP = {"sh", "bash", "zsh", "dash", "ksh", "cmd", "powershell", "pwsh"}


def _wrapped(seg):
    """(inner command, is_powershell) of `bash -c '...'`, `cmd /c ...`, `powershell -Command ...`, `eval ...`."""
    if not seg or _base(seg[0]) in READ_CMDS:  # echo bash -c ... only prints
        return None
    for k, t in enumerate(seg):
        b = _base(t)
        if b == "eval":
            return " ".join(seg[k + 1:]), False
        if b in SHELL_WRAP:
            j = next((j for j in range(k + 1, len(seg)) if re.fullmatch(r"[-/](?:c|k|com\w*)", seg[j].lower())), None)
            return (" ".join(seg[j + 1:]), b in ("powershell", "pwsh")) if j is not None else None
    return None


def _segments(cmd):
    """Words per simple command, split on ; & | && || and newlines. Raises ValueError on unbalanced quotes."""
    import shlex
    cmd = re.sub(r"\\(?![\\\"'`$\n])", "/", cmd).replace("\n", " ; ")
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split, lex.commenters = True, ""
    segs, cur = [], []
    for t in lex:
        if t and set(t) <= set(";&|"):
            segs.append(cur)
            cur = []
        elif t not in ("(", ")", "{", "}"):
            cur.append(t)
    segs.append(cur)
    return [s for s in segs if s]


def _cfg_bad(v):
    """A `git -c` / --config-env value that drops hooks, directly or through an alias."""
    import shlex
    if HOOKS_KEY.search(v):
        return True
    m = re.match(r"alias\.[^=]+=(.*)", v, re.I | re.S)
    if not m:
        return False
    try:
        val = m.group(1)
        return bypass_hit(val[1:]) if val.startswith("!") else _git_bypass(shlex.split(val))
    except ValueError:
        return True


def _git_bypass(words):
    """words after `git`: --no-verify (any subcommand), commit -n, writes to core.hooks*."""
    i = 0
    while i < len(words):
        w = words[i]
        if w in ("-c", "--config-env"):
            if i + 1 < len(words) and _cfg_bad(words[i + 1]):
                return True
            i += 2
        elif w.startswith("--config-env="):
            if _cfg_bad(w.split("=", 1)[1]):
                return True
            i += 1
        elif w in GIT_ARG_OPTS:
            i += 2
        elif w.startswith("-"):
            i += 1
        else:
            break
    if i >= len(words):
        return False
    sub, rest = words[i].lower(), words[i + 1:]
    free = set()
    for j, t in enumerate(rest):
        if j in free:
            continue
        if t in GIT_TEXT_OPTS:
            free.add(j + 1)
            continue
        if t.startswith("--") and t.split("=", 1)[0] in GIT_TEXT_OPTS:
            continue
        if t.lower().startswith("--no-veri"):
            return True
        if sub == "commit" and re.match(r"-[^-]", t):
            for k, c in enumerate(t[1:]):
                if c == "n":
                    return True
                if c in "mFCct":
                    if k == len(t) - 2:
                        free.add(j + 1)
                    break
                if c in "Su":  # optional attached value
                    break
        if sub != "config" and HOOKS_KEY.search(t):
            return True
    if sub == "config":
        low = [t.lower() for t in rest]
        if any(t in ("-e", "--edit", "edit") for t in low) or (
                "core" in low and any(t.lstrip("-") in ("remove-section", "rename-section") for t in low)):
            return True
        if any(HOOKS_KEY.search(t) for t in low):
            opts = [t for t in low if t.startswith("-")]
            pos = [t for t in low if not t.startswith("-")]
            if pos[:1] == ["get"]:
                pos = pos[1:]
            return not (len(pos) == 1 and all(o in CFG_READ_OPTS or o.startswith(("--type=", "--default="))
                                               for o in opts))
    return False


def bypass_hit(cmd, ps=False, depth=0):
    """A shell command that skips the pre-commit hook (and its secret scan)."""
    cmd = _prep(cmd, ps)
    if depth < 3 and any(bypass_hit(s, ps, depth + 1) for s in _subs(cmd)):
        return True
    try:
        segs = _segments(cmd)
    except ValueError:
        return bool(re.search(r"\bgit\b", cmd, re.I) and re.search(r"--no-veri|core\.hooks|\scommit\b[^;|&\n]*\s-[a-z]*n",
                                                                    cmd, re.I))
    for s in segs:
        w = _wrapped(s)
        if w and depth < 3 and bypass_hit(w[0], w[1], depth + 1):
            return True
        g = next((k for k, t in enumerate(s) if _base(t) == "git"), None)
        if g is None:
            if _base(s[0]) not in READ_CMDS and any(HOOKS_KEY.search(t) for t in s):
                return True
        elif any(HOOKS_KEY.search(t) for t in s[:g]) or _git_bypass(s[g + 1:]):
            return True
    return False


def _python_ok(args):
    i = 0
    while i < len(args) and args[i].startswith("-") and args[i] not in ("-m", "-c", "-"):
        i += 2 if args[i] in ("-W", "-X") else 1
    if i >= len(args) or args[i] in ("-c", "-"):
        return False
    if args[i] == "-m":
        return args[i + 1:i + 2] == ["pytest"] and _pytest_ok(args[i + 2:])
    return not any(_prot(t) for t in args[i + 1:])  # running a hook script reads it; its arguments may not name one


def _pytest_ok(args):
    for j, t in enumerate(args):
        if _prot(t) and (t.startswith("-") or (j and args[j - 1].startswith("-") and not PYTEST_FLAG.match(args[j - 1]))):
            return False
    return True


def _seg_reads_only(seg):
    words, i = [], 0
    while i < len(seg):
        t = seg[i]
        if t and set(t) <= set("<>&|0123456789") and ("<" in t or ">" in t):  # redirection operator
            if ">" in t and i + 1 < len(seg) and _prot(seg[i + 1]):
                return False
            i += 2
            continue
        words.append(t)
        i += 1
    if not words:
        return True
    if re.match(r"[\w$:.]+=", words[0]):  # VAR=value prefix (GIT_EXTERNAL_DIFF=..., etc.)
        return False
    cmd, args = _base(words[0]), words[1:]
    for j, a in enumerate(args):
        m = OUT_OPT.match(a)
        if m and (_prot(m.group(1)) if m.group(1) is not None else j + 1 < len(args) and _prot(args[j + 1])):
            return False
    if cmd in ("cd", "pushd", "popd", "set-location", "sl", "chdir"):
        return not any(_prot(a) and not re.search(r"(?:^|/)tools$", _norm(a)) for a in args)
    if cmd in READ_CMDS:
        return True
    if cmd == "pytest":
        return _pytest_ok(args)
    if cmd in ("python", "python3", "py"):
        return _python_ok(args)
    if cmd == "git":
        i = 0
        while i < len(args) and args[i].startswith("-"):
            if args[i] in ("-c", "--config-env") or args[i].startswith(("--config-env", "--exec-path")):
                return False
            i += 2 if args[i] in GIT_ARG_OPTS else 1
        return i < len(args) and args[i].lower() in GIT_READ and not any(
            a.startswith(("-O", "--open-files-in-pager")) for a in args[i + 1:])
    return False


def shell_writes_protected(cmd, ps=False, depth=0):
    """A shell command naming a hook/settings path that isn't a plain read (cat, grep, pytest, git diff...)."""
    cmd = _prep(cmd, ps)
    if depth < 3 and any(shell_writes_protected(s, ps, depth + 1) for s in _subs(cmd)):
        return True
    if not SHELL_GATE.search(cmd):
        return False
    try:
        segs = _segments(cmd)
    except ValueError:
        return bool(SHELL_PROT.search(_norm(cmd)))
    if not any(_prot(t) for s in segs for t in s):
        return False
    return not all(_seg_reads_only(s) for s in segs)


def pre():
    d = json.load(sys.stdin)
    tool, inp = d.get("tool_name", ""), d.get("tool_input") or {}
    if tool in ("Bash", "PowerShell"):
        cmd, ps = inp.get("command", ""), tool == "PowerShell"
        lights, flats = shell_forms(cmd, ps)  # every check runs on the raw text and on the unquoted forms
        if any(GIT_PUSH.search(t) for t in flats):
            return deny("git push is blocked")
        if any(DANGER.search(t) for t in flats):
            return deny("Command matches the DANGER list")
        if any(env_hit(t) for t in flats) and not safe_env_grep(cmd):  # safe_env_grep lexes like the shell
            return deny(".env access blocked; inspect it only with a bare `grep -v PRIVATE_KEY <file>`")
        if any(bypass_hit(t, ps) for t in lights):
            return deny(HF2)
        if SELF_PROTECT and any(shell_writes_protected(t, ps) for t in lights):
            return deny(HF3)
    else:
        path = inp.get("file_path") or inp.get("path") or inp.get("notebook_path") or ""
        if SELF_PROTECT and tool in ("Edit", "Write", "MultiEdit", "NotebookEdit") and EDIT_PROT.search(_norm(path)):
            return deny(HF3)
        if env_hit(path) or (tool == "Grep" and grep_reads_env(inp)) \
                or (tool == "Glob" and "env" in (inp.get("pattern") or "").lower()):
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
