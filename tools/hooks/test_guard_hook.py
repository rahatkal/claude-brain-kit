"""Tests for guard_hook.pre(). Trigger strings are built by concatenation so this file stays editable under the hook.
Run: python -m pytest -q tools/hooks/test_guard_hook.py"""
import io, json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import guard_hook  # noqa: E402

E = "." + "env"            # the secrets file name
PUSH = "pu" + "sh"


@pytest.fixture(autouse=True)
def no_fire_log(monkeypatch):
    monkeypatch.setattr(guard_hook, "log_fire", lambda *a: None)


def reason(monkeypatch, capsys, tool, **inp):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": tool, "tool_input": inp})))
    guard_hook.pre()
    out = capsys.readouterr().out.strip()
    return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] if out else ""


def run(monkeypatch, capsys, tool, **inp):
    return "deny" if reason(monkeypatch, capsys, tool, **inp) else "allow"


def bash(monkeypatch, capsys, cmd):
    return run(monkeypatch, capsys, "Bash", command=cmd)


# --- .env: the PRIVATE_KEY exemption needs a real, bare grep -------------------
@pytest.mark.parametrize("cmd", [
    f"cat {E} # grep -v PRIVATE_KEY",
    f"cat {E}; grep -v PRIVATE_KEY {E}",
    f"grep -v PRIVATE_KEY {E} && cat {E}",
    f"grep -v PRIVATE_KEY {E} | cat {E}",
    f"grep -v PRIVATE_KEY {E} `cat {E}`",
    f"grep -v PRIVATE_KEY {E} $(cat {E})",
    f"grep -v PRIVATE_KEY {E} > out.txt",
    f"grep -v PRIVATE_KEY {E} other{E}",
    f"grep -v PRIVATE_KEY {E} | grep -v x {E}.prod",
])
def test_env_exemption_needs_real_grep(monkeypatch, capsys, cmd):
    assert bash(monkeypatch, capsys, cmd) == "deny"


# --- git push hidden behind global options -------------------------------------
@pytest.mark.parametrize("cmd", [
    f"git --work-tree . {PUSH} origin main",
    f"git --git-dir x/.git {PUSH}",
    f"git --exec-path /usr/lib {PUSH} origin",
    f"git -p {PUSH}",
    f'git -C "my repo" {PUSH}',
    f"git --git-dir=x/.git {PUSH}",
    f"git -c alias.p={PUSH} p",
    f"git commit -m x && git {PUSH}",
    f"git.exe {PUSH} origin",
    f'& "C:\\Program Files\\Git\\bin\\git.exe" {PUSH}',
])
def test_git_push_with_flags(monkeypatch, capsys, cmd):
    assert bash(monkeypatch, capsys, cmd) == "deny"


def test_grep_glob_env(monkeypatch, capsys):
    assert run(monkeypatch, capsys, "Grep", pattern="KEY", path="C:/proj/x", glob="*" + E + "*") == "deny"
    assert run(monkeypatch, capsys, "Grep", pattern="KEY", glob="*env*") == "deny"
    assert run(monkeypatch, capsys, "Glob", pattern="**/*" + E + "*") == "deny"


def test_recursive_grep_on_dir_with_env(monkeypatch, capsys, tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / E).write_text("X=1")
    assert run(monkeypatch, capsys, "Grep", pattern="X", path=str(tmp_path)) == "deny"
    assert run(monkeypatch, capsys, "Grep", pattern="X", path=str(tmp_path), glob="*") == "deny"
    assert run(monkeypatch, capsys, "Grep", pattern="X", path=str(tmp_path), glob="*.py") == "allow"
    assert run(monkeypatch, capsys, "Grep", pattern="X", path=str(tmp_path), type="py") == "allow"


def test_grep_on_clean_dir_allowed(monkeypatch, capsys, tmp_path):
    (tmp_path / "a.py").write_text("x")
    assert run(monkeypatch, capsys, "Grep", pattern="X", path=str(tmp_path)) == "allow"


@pytest.mark.parametrize("name", [E + ".production.bak", E + ".prod.old", E + ".local.save", E + ".example.bak", E + "*"])
def test_env_backup_names(monkeypatch, capsys, name):
    assert bash(monkeypatch, capsys, f"cat config/{name}") == "deny"
    assert run(monkeypatch, capsys, "Read", file_path=f"C:/proj/{name}") == "deny"


def test_long_content_is_fast(monkeypatch, capsys):
    import time
    t = time.time()
    assert run(monkeypatch, capsys, "Write", file_path="C:/x/a.py", content="A_" * 200000) == "allow"
    assert time.time() - t < 2


# --- basic denies --------------------------------------------------------------
@pytest.mark.parametrize("cmd", [
    f"cat {E}", f"type proj\\{E}", f"cat {E}.local",
    f"git {PUSH}", f"git {PUSH} origin main", f"git -C repo {PUSH}",
    "rm -" + "rf /", "rm -" + "rf ~/notes", "psql -c 'DROP " + "TABLE users'", "deploy --force --env " + "prod",
])
def test_basic_denies(monkeypatch, capsys, cmd):
    assert bash(monkeypatch, capsys, cmd) == "deny"


def test_danger_reason(monkeypatch, capsys):
    assert "DANGER" in reason(monkeypatch, capsys, "Bash", command="rm -" + "rf /")


def test_basic_read_deny(monkeypatch, capsys):
    assert run(monkeypatch, capsys, "Read", file_path=f"C:/proj/{E}") == "deny"
    assert run(monkeypatch, capsys, "Edit", file_path=f"C:/proj/{E}", old_string="a", new_string="b") == "deny"


# --- legit commands still allowed ----------------------------------------------
@pytest.mark.parametrize("cmd", [
    "git status", "git log --oneline -5", 'git commit -m "fix hook"', "git diff",
    f'git commit -m "notes: {PUSH}ed 4 drafts"', f"git log --grep={PUSH}",
    f"git add -A && git commit -m 'block {PUSH} loophole'",
    "cat README.md", "python -m pytest -q", "echo pushups", "rm -rf build", "sh setup.sh",
    "python tools/precheck_note.py .drafts/topic.md", "python tools/secret_scan.py",
    f"grep -v PRIVATE_KEY {E}",
    f"grep -v PRIVATE_KEY proj/{E}",
    f'grep -v PRIVATE_KEY "C:/Users/me/app/{E}"',
    f'grep -v PRIVATE_KEY {E} | grep -v -i "key\\|secret\\|pass"',
    f"grep -v PRIVATE_KEY {E} | head -n 20",
    f"cat {E}.example", f"cp {E}.sample x", "echo $HOME",
])
def test_legit_allowed(monkeypatch, capsys, cmd):
    assert bash(monkeypatch, capsys, cmd) == "allow"


def test_legit_tools_allowed(monkeypatch, capsys):
    assert run(monkeypatch, capsys, "Read", file_path="C:/x/notes/a.md") == "allow"
    assert run(monkeypatch, capsys, "Read", file_path=f"C:/x/{E}.example") == "allow"
    assert run(monkeypatch, capsys, "Edit", file_path="C:/x/a.py", old_string="a", new_string="b = 1") == "allow"
    assert run(monkeypatch, capsys, "Grep", pattern="x", glob="*.md") == "allow"
    assert run(monkeypatch, capsys, "Glob", pattern="**/*.py") == "allow"


# --- commit hook bypass ----------------------------------------------------------
NV = "--no-" + "verify"
HP = "core." + "hooks" + "Path"
HF2 = guard_hook.HF2


@pytest.mark.parametrize("cmd", [
    f"git commit {NV} -m x", f'git commit -m "x" {NV}', "git commit -n -m x", "git commit -nm x",
    "git commit -anm x", "git commit -an -m x", f"git -C . commit {NV}", "git commit --no-" + "veri -m x",
    f"git merge {NV} dev", "git add -A && git commit -nm x", f"git.exe commit {NV}",
    f"git config {HP} /dev/null", f"git config --local {HP} x", f"git config --unset {HP}",
    f"git config --unset-all {HP}", f"git config set {HP} x", f"git config unset {HP}",
    f"git config --global {HP.upper()} x", "git config core." + "hooksDir x", "git config --remove-section core",
    f"git -c {HP}=/dev/null commit -m x", f'git -c "{HP}=x" commit -m x', f"git --config-env={HP}=V commit -m x",
    f'git -c alias.ci="commit {NV}" ci -m x', "git -c alias.ci='commit -n' ci -m x",
    f"GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0={HP} GIT_CONFIG_VALUE_0=x git commit -m y",
    f'git commit -m "$(git config {HP} x)"',
])
def test_hook_bypass_denied(monkeypatch, capsys, cmd):
    for tool in ("Bash", "PowerShell"):
        assert HF2 in reason(monkeypatch, capsys, tool, command=cmd), (tool, cmd)


def test_hook_bypass_powershell_forms_denied(monkeypatch, capsys):
    for cmd in ("git commit --no-`" + "verify -m x", f"$env:GIT_CONFIG_PARAMETERS = \"'{HP}'='x'\"; git commit -m y"):
        assert run(monkeypatch, capsys, "PowerShell", command=cmd) == "deny", cmd


@pytest.mark.parametrize("cmd", [
    f'git commit -m "docs: guard denies {NV} now"', "git commit -m 'block -n flag'", 'git commit -m "-n is blocked"',
    "git commit -am fix", "git commit -mnothing", "git commit -F msg.txt", "git commit --amend --no-edit",
    "git config user.name Me", f"git config {HP}", f"git config --get {HP}", "git log -n 5",
    f"git log --grep={NV}", "git status; echo -n hi",
    f"git commit -m \"$(cat <<'EOF'\nguard: deny {NV} and {HP} writes\nEOF\n)\"",
])
def test_legit_git_allowed(monkeypatch, capsys, cmd):
    assert bash(monkeypatch, capsys, cmd) == "allow"
    assert run(monkeypatch, capsys, "PowerShell", command=cmd) == "allow"


# --- hooks and settings are owner-only (SELF_PROTECT) ----------------------------
H = "tools/" + "hooks/guard_hook.py"
HF3 = guard_hook.HF3


@pytest.fixture
def protect(monkeypatch):
    monkeypatch.setattr(guard_hook, "SELF_PROTECT", True, raising=False)


def test_self_protect_ships_on():
    assert guard_hook.SELF_PROTECT is True


@pytest.mark.parametrize("path", [
    "C:/Users/me/brain/" + H, "C:\\Users\\me\\brain\\tools\\hooks\\guard_hook.py",
    "C:/x/TOOLS/Hooks/Pre-Commit", "./" + H, "C:/x/tools/foo/../hooks/guard_hook.py", "C:/x/tools//hooks/new.py",
    "C:/x/.claude/settings.json", "C:\\x\\.Claude\\Settings.Local.JSON", "C:/Users/me/.claude/settings.json",
    "C:/x/.git/config",
])
def test_edit_protected_denied(monkeypatch, capsys, protect, path):
    assert HF3 in reason(monkeypatch, capsys, "Edit", file_path=path, old_string="a", new_string="b")
    assert HF3 in reason(monkeypatch, capsys, "Write", file_path=path, content="b")
    assert HF3 in reason(monkeypatch, capsys, "MultiEdit", file_path=path, edits=[{"old_string": "a", "new_string": "b"}])


def test_notebook_and_reads(monkeypatch, capsys, protect):
    assert run(monkeypatch, capsys, "NotebookEdit", notebook_path="C:/x/tools/hooks/a.ipynb", new_source="x") == "deny"
    assert run(monkeypatch, capsys, "Read", file_path="C:/x/" + H) == "allow"
    assert run(monkeypatch, capsys, "Grep", pattern="deny", path="C:/x/tools/hooks", glob="*.py") == "allow"
    for p in ("C:/x/tools/precheck_note.py", "C:/x/.claude/agents/verifier.md", "C:/x/src/hooks/useAuth.ts",
              "C:/x/notes/tools-hooks.md", "C:/x/.claude/worktrees/w/notes/a.md"):
        assert run(monkeypatch, capsys, "Write", file_path=p, content="x") == "allow", p


def test_switch_off_allows(monkeypatch, capsys):
    monkeypatch.setattr(guard_hook, "SELF_PROTECT", False, raising=False)
    assert run(monkeypatch, capsys, "Edit", file_path="C:/x/" + H, old_string="a", new_string="b") == "allow"
    assert bash(monkeypatch, capsys, f"rm {H}") == "allow"


@pytest.mark.parametrize("cmd", [
    f"echo x > {H}", "echo x >> tools\\hooks\\guard_hook.py", f"cat a | tee {H}", f"sed -i s/a/b/ {H}",
    f"cp /tmp/x {H}", f"mv {H} /tmp/x", f"rm {H}", "rm -rf tools/" + "hooks", "del tools\\hooks\\guard_hook.py",
    f"Remove-Item {H}", f"Set-Content -Path {H} -Value x", f"'x' | Out-File {H}", f"Copy-Item x {H}",
    f"Move-Item {H} y", f"python -c \"open('{H}','w').write('')\"", f"python - <<EOF\nopen('{H}','w')\nEOF",
    "echo {} > .claude/settings.json", "echo {} > .claude\\settings.local.json", f"git checkout -- {H}",
    "rm tools/h*/g*.py", "cd tools/hooks && echo x > guard_hook.py", f"echo {H} | xargs rm",
    f'git commit -m "$(rm {H})"', "cat x > C:/Users/me/brain/tools/hooks/pre-commit",
    f"python tools/x.py {H}", "cp x settings.local.json", "python -m pytest --basetemp=tools/hooks",
    f"git diff --output={H}", "cd .claude && echo x > settings.json", f"perl -pi -e s/a/b/ {H}",
])
def test_shell_writes_denied(monkeypatch, capsys, protect, cmd):
    for tool in ("Bash", "PowerShell"):
        assert HF3 in reason(monkeypatch, capsys, tool, command=cmd), (tool, cmd)


@pytest.mark.parametrize("cmd", [
    f"cat {H}", f"grep -n deny {H}", f"head -n 20 {H}", f"tail -5 {H}", "python -m pytest -q tools/hooks/test_guard_hook.py",
    f"python {H} pre", f"python {H} pre < probe.json", f"git diff {H}", f"git add {H}",
    f'git commit -m "guard: harden {H}"', "git log -p -- tools/hooks", f"Get-Content {H}",
    f"Select-String -Path {H} -Pattern deny", "cat .claude/settings.json", f"cat {H} > /tmp/copy.py",
    f"wc -l {H} tools/precheck_note.py", "python tools/precheck_note.py notes/a.md", "ls tools/hooks",
    "cd C:/x && python -m pytest -q tools/hooks", "echo hi > out.txt", "grep -rn 'tools/hooks' notes",
    f"git status && python -m pytest -q {H.replace('guard_hook', 'test_guard_hook')}",
])
def test_shell_reads_allowed(monkeypatch, capsys, protect, cmd):
    assert bash(monkeypatch, capsys, cmd) == "allow"
    assert run(monkeypatch, capsys, "PowerShell", command=cmd) == "allow"
