"""Shell-unquoting tests: bash strips '' "" and \\ before running, so the hook must match the unquoted form too.
Same file in .drafts/guard-patch (vault, patched hook) and .drafts/kit-guard (kit hook); trigger words are concatenated."""
import importlib.util, io, json, sys
from pathlib import Path

import pytest

_here = Path(__file__).parent
_path = next(p for p in (_here / "guard_hook.patched.py", _here / "guard_hook.py") if p.exists())
_spec = importlib.util.spec_from_file_location("guard_hook", _path)
gh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gh)

E, PU, NV, HP = "." + "env", "pu" + "sh", "--no-" + "verify", "core." + "hooks" + "Path"
EN, EV = ".e" + "n", ".e"   # halves of the secrets name, to splice escapes in
VAULT = hasattr(gh, "LIVE")  # vault-only checks (live trading, maintenance window)


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(gh, "log_fire", lambda *a: None)
    monkeypatch.delenv("GUARD_" + "MAINT", raising=False)


def run(monkeypatch, capsys, tool, cmd):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": tool, "tool_input": {"command": cmd}})))
    gh.pre()
    return "deny" if capsys.readouterr().out.strip() else "allow"


# --- fuzzer survivor shapes (tools/ultron_fuzz.py) that a real shell runs ----------------------------
BASH_DENY = [
    f"cat {EN}''v", f'cat {EV}""nv', f"cat {EV}\\nv", "cat .\\" + E[1:], f"CAt \t {EN}''v", f"$(caT {EN}''v)",
    f"sh -c 'cat '.\\{E[1:]}''", f'echo ok | bash -c "cat {EV}""nv"', f"c\\at {EN}\"\"v", f"X=1\tcat {EN}''v",
    f"type {EV}\\nv", f"head -n 3 ./.\\{E[1:]}", f"cmd /c type {EV}^nv",
    f"g\\it {PU} origin master", f"git p\\ush origin master", f'g""it -C . {PU}', f"git -''C . {PU}",
    f"git -C . p\\ush", "\ng\\it\t-C \t . \t " + PU,
    f"git commit -m x --no-v\\erify", f"sh -c 'git commit -m x {NV}'", f'powershell -c "G""it commit -m x {NV}"',
    "bash -c \"git commit -nm x\"", "git com\\mit -nm x", "g\\it commit -nm x", f"git '\\commit' -nm x",
    "eval 'git commit -n -m x'", "timE git config core.h\\ooksPath /tmp/x", f"git -c {HP[:7]}''{HP[7:]}=x commit -m y",
    "rm tools/ho''oks/x.py", "echo x > tools/hoo\\ks/guard_hook.py",
]
PS_DENY = [
    f'Get-Content {EV}""nv', f"Get-Content .''{E[1:]}", f"Get-Content {EV}`nv", f"Get-Co''ntent {EN}''v",
    f'bash -c "cat .\\{E[1:]}"', f"g`it {PU} origin master", f'gi""t {PU} origin master',
    f"git commit -m x --no-ver`ify",
]


@pytest.mark.parametrize("cmd", BASH_DENY)
def test_bash_unquoted_forms_denied(monkeypatch, capsys, cmd):
    assert run(monkeypatch, capsys, "Bash", cmd) == "deny", cmd


@pytest.mark.parametrize("cmd", PS_DENY)
def test_powershell_unquoted_forms_denied(monkeypatch, capsys, cmd):
    assert run(monkeypatch, capsys, "PowerShell", cmd) == "deny", cmd


@pytest.mark.skipif(not VAULT, reason="vault-only checks")
@pytest.mark.parametrize("cmd", ["python bot.py --l''i" + "ve", "python l\\ive" + "_trader.py",
                                 "setx GUARD_MA''INT 2026-01-01T00:00", "set GUARD_\\MAINT=x"])
def test_vault_checks_unquoted(monkeypatch, capsys, cmd):
    assert run(monkeypatch, capsys, "Bash", cmd) == "deny", cmd


# --- ordinary commands with quotes or backslashes stay allowed ----------------------------------------
BASH_OK = [
    'git commit -m "it\'s fine"', "git commit -m 'block -n flag'", 'git commit -m "-n is blocked"',
    f'git commit -m "docs: guard denies {NV} now"', f'git commit -m "x: {PU}ed 4 drafts"', f'git log --grep="{PU}"',
    'echo "a\\nb"', "echo 'it''s'", 'echo "" && git status', r"cat C:\Users\x\notes.md", r"type C:\Users\x\notes.md",
    r"cd C:\Users\x\Desktop && git status", "python -m pytest -q", f"grep -v PRIVATE_KEY {E}",
    f'grep -v PRIVATE_KEY {E} | grep -v -i "key\\|secret\\|pass"', 'echo "git commit -n"', "sh -c 'git status'",
    "cmd /c dir", f"cat {E}.example", 'grep -rn "tools/hooks" notes', r"python tools\x.py C:\Users\x\notes\a.md",
]
PS_OK = [
    'git commit -m "it\'s fine"', 'Write-Host "a`tb"', "Get-Content C:\\Users\\x\\notes.md",
    "& .\\" + E[1:] + "\\Scripts\\Activate.ps1", "Get-ChildItem .\\" + E[1:] + "s", 'echo "a\\nb"',
    "git log --oneline -5", "Get-Content 'C:\\x\\it''s.md'",
]


@pytest.mark.parametrize("cmd", BASH_OK)
def test_bash_ordinary_quotes_allowed(monkeypatch, capsys, cmd):
    assert run(monkeypatch, capsys, "Bash", cmd) == "allow", cmd


@pytest.mark.parametrize("cmd", PS_OK)
def test_powershell_ordinary_quotes_allowed(monkeypatch, capsys, cmd):
    assert run(monkeypatch, capsys, "PowerShell", cmd) == "allow", cmd


def test_unshell_forms():
    assert gh.unshell(f"cat {EN}''v") == (f"cat {E}", f"cat {E}")
    assert gh.unshell("cat .\\" + E[1:]) == (f"cat {E}", f"cat {E}")
    assert gh.unshell(f"a  \t 'b' \"c\"") == ("a  \t 'b' \"c\"", "a b c")
    assert gh.unshell(f"Get-Content {EV}`nv", ps=True)[1] == f"Get-Content {E}"
    assert gh.unshell("Get-Content .\\" + E[1:], ps=True)[1] == "Get-Content .\\" + E[1:]  # \ is a path in PowerShell
