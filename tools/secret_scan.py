"""Secret scanner for the second-brain pre-commit hook (stdlib only).

Usage:
  python tools/secret_scan.py --staged   # scan lines added in the index (hook mode); exit 1 on a hit
  python tools/secret_scan.py --all      # read-only report over `git ls-files` (index content)

A line containing "secret-scan: allow" is skipped. Matches are always masked.
"""
import re
import subprocess
import sys

ALLOW = "secret-scan: allow"
HEX64 = r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])"
STRONG = re.compile(r"(?i)priv|secret|mnemonic|seed")
KEYWORD = re.compile(r"(?i)key")
NEAR = 40  # key word must be within this many chars of the hex (minified HTML lines are huge)
# 0x+64 hex is also a tx hash / condition id; skip hash-labelled lines unless a strong key word is present.
HASHWORD = re.compile(r"(?i)\btx|hash|condition|market|token_?id|block|sha|commit")
PLACEHOLDER = re.compile(
    r"(?i)^(?:x+|\*+|\.+|-+|<.*>|\$\{?\w*\}?|none|null|nil|true|false|str|bytes|"
    r"your[_-]?\w*|changeme|change_me|example\w*|placeholder|dummy|fake|test\w*|redacted|todo|tbd|"
    r"os\.\S*|getenv\S*|env\S*)$"
)

RULES = [
    ("pem-private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    # base62 run only, so hyphenated slugs/CSS names (sk-toggle-mega-...) never match
    ("openai-key", re.compile(r"(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-|admin-)?(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{20,}")),
    ("aws-access-key", re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")),
    ("github-token", re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}")),
    ("slack-token", re.compile(r"xox[bp]-[A-Za-z0-9-]{10,}")),
    ("telegram-bot-token", re.compile(r"(?<![0-9])\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])")),
]
EVM_0X = re.compile(r"0x[0-9a-fA-F]{64}(?![0-9a-fA-F])")
BARE_HEX = re.compile(HEX64)
ASSIGN = re.compile(
    r"\b[A-Z0-9_]*(?:PRIVATE_KEY|API_KEY|SECRET|PASSWORD)[A-Z0-9_]*\s*[:=]\s*['\"]?([^\s'\"`#,;)]*)"
)


def mask(s):
    return s[:4] + "***"


def scan_line(line):
    """Return [(rule, masked_match)] for one line."""
    if ALLOW in line:
        return []
    hits = []
    for name, rx in RULES:
        for m in rx.finditer(line):
            hits.append((name, mask(m.group(0))))
    for rx, rule in ((EVM_0X, "evm-private-key"), (BARE_HEX, "hex-key-near-keyword")):
        for m in rx.finditer(line):
            if rx is BARE_HEX and line[max(0, m.start() - 2):m.start()].lower() == "0x":
                continue  # already handled as 0x form
            near = line[max(0, m.start() - NEAR):m.end() + NEAR]
            keyish = bool(STRONG.search(near)) or (bool(KEYWORD.search(near)) and not HASHWORD.search(near))
            if keyish or (rx is EVM_0X and not HASHWORD.search(line)):
                hits.append((rule, mask(m.group(0))))
    for m in ASSIGN.finditer(line):
        v = m.group(1)
        if len(v) >= 6 and not PLACEHOLDER.match(v) and "(" not in v and "[" not in v:
            hits.append(("secret-assignment", mask(v)))
    return hits


def scan_text(path, text):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for rule, m in scan_line(line):
            out.append((path, i, rule, m))
    return out


def _git(*args):
    return subprocess.run(["git", "-c", "core.quotepath=off", *args],
                          capture_output=True, check=True).stdout


def parse_diff(diff):
    """Yield (path, new_line_no, text) for added lines of a unified diff with -U0."""
    path, in_hunk, n = None, False, 0
    hunk = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for raw in diff.split("\n"):
        if raw.startswith("diff --git "):
            path, in_hunk = None, False
        elif not in_hunk and raw.startswith("+++ "):
            p = raw[4:]
            path = p[2:] if p.startswith("b/") else p
        elif raw.startswith("@@"):
            m = hunk.match(raw)
            if m:
                in_hunk, n = True, int(m.group(1))
        elif in_hunk and raw.startswith("+"):
            yield path, n, raw[1:].rstrip("\r")
            n += 1
        elif in_hunk and raw.startswith(" "):
            n += 1


def scan_staged():
    diff = _git("diff", "--cached", "-U0", "--no-color", "--no-ext-diff",
                "--diff-filter=ACMR").decode("utf-8", "replace")
    out = []
    for path, n, text in parse_diff(diff):
        for rule, m in scan_line(text):
            out.append((path, n, rule, m))
    return out


def scan_all():
    """Read-only scan of every tracked file's index content (one git process)."""
    paths = [p for p in _git("ls-files", "-z").decode("utf-8", "replace").split("\0") if p]
    req = "".join(":" + p + "\n" for p in paths).encode("utf-8")
    data = subprocess.run(["git", "cat-file", "--batch"], input=req,
                          capture_output=True, check=True).stdout
    out, pos = [], 0
    for path in paths:
        nl = data.index(b"\n", pos)
        header = data[pos:nl].split()
        pos = nl + 1
        if len(header) < 3 or header[1] == b"missing":
            continue
        size = int(header[2])
        blob, pos = data[pos:pos + size], pos + size + 1
        if b"\0" in blob[:8000]:
            continue  # binary
        out.extend(scan_text(path, blob.decode("utf-8", "replace")))
    return out


def main(argv):
    mode = argv[1] if len(argv) > 1 else "--staged"
    hits = scan_all() if mode == "--all" else scan_staged()
    for path, n, rule, m in hits:
        print(f"BLOCKED secret? {path}:{n} {rule} {m}")
    if hits and mode != "--all":
        print(f"{len(hits)} possible secret(s). Remove them, or mark a known-safe line with '{ALLOW}'.")
    return 1 if hits and mode != "--all" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
