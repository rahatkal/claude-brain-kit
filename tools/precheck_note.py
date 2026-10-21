"""Free structural/number check on a draft note, run BEFORE the Haiku verifier.

Usage: python tools/precheck_note.py .drafts/<topic>.md [.drafts/<topic>.src.txt]
Exit 0 = structure OK (pass the UNMATCHED list to the verifier), 1 = fix the draft first.
"""
import re
import sys
from pathlib import Path

NUM = re.compile(r"(?<![\w.])~?\$?\d[\d,]*(?:\.\d+)?(?:%|k|m)?", re.I)
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
STALEY = re.compile(r"[$\u20b9\u20ac\u00a3]\s?\d[\d,.]*\s*(?:k|m)?\s*(?:/|per\s+)(?:mo|month|yr|year|user|seat|m\b|million)|\d[\d,.]*\s*[km]?\s+stars\b", re.I)

# #13 injection guard: flag imperative directives that may have been copied from an
# untrusted .src.txt into the note body, where they'd later read as instructions when
# the note loads into context. WARN only (never blocks) — this is a security-research
# brain, so notes legitimately DISCUSS injection; a quoted/backticked/parenthetical
# example is treated as defanged and stays silent.
INJECT = re.compile(
    r"ignore\s+(all\s+|the\s+|your\s+|any\s+)?(previous|prior|above|earlier|preceding)\s+"
    r"(instruction|prompt|rule|message|direction)"
    r"|disregard\s+(all\s+|the\s+|your\s+|previous\s+|prior\s+)"
    r"|override\s+(your\s+|the\s+)?(instruction|rule|system|prompt)"
    r"|new\s+instructions?\s*:"
    r"|you\s+(must|should|will)\s+now\s+"
    r"|^\s*system\s*:"
    r"|(?<![\w-])ACTION\s*:\s*\w",
    re.I,
)
QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'|`[^`]*`|\([^)]*\)")


def digits(s):
    return s.replace(",", "")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    note = Path(sys.argv[1])
    src = Path(sys.argv[2]) if len(sys.argv) > 2 else note.with_name(note.stem + ".src.txt")
    text = note.read_text(encoding="utf-8")
    lines = text.splitlines()
    fails, warns = [], []

    if not re.match(r"[a-z0-9]+(-[a-z0-9]+)*\.md$", note.name):
        fails.append(f"filename not lowercase-hyphen: {note.name}")
    if not any(l.startswith("verified:") for l in lines[:5]):
        fails.append("no 'verified:' line in the first 5 lines")
    # freshness (research-engineering): every note records when its claims were last checked
    # against the source, and how long they stay fresh; tools/stale_notes.py flags expired ones.
    fm = text.split("\n---", 1)[0] if text.startswith("---") else "\n".join(lines[:8])
    if not re.search(r"^last_checked:\s*\d{4}-\d{2}-\d{2}\s*$", fm, re.M):
        fails.append("no 'last_checked: YYYY-MM-DD' in frontmatter")
    if not re.search(r"^fresh_days:\s*\d+\s*$", fm, re.M):
        fails.append("no 'fresh_days: N' in frontmatter (30 prices/stars/models, 90 tools/repos, 365 papers/concepts)")

    heads = [l.strip().lower() for l in lines if l.startswith("## ")]
    if not heads or not heads[0].startswith("## key findings"):
        fails.append("first section must be '## Key findings'")
    # "not searched" list: what this note did NOT check, so a gap reads as a gap, not as "ruled out"
    if "## not checked" not in heads:
        fails.append("missing '## Not checked' section (list what wasn't searched/verified, or '- nothing material')")
    if not heads or heads[-1] != "## sources":
        fails.append("last section must be '## Sources'")
    elif not re.search(r"https?://", text.split("## Sources")[-1]):
        fails.append("'## Sources' has no URL")

    in_kf, volatile = False, []
    for l in lines:
        if l.startswith("## "):
            in_kf = l.lower().startswith("## key findings")
        # STALE (deterministic, so it doesn't depend on the verifier): prices and star counts
        # in Key findings decay fast, so each one needs an "as of <date>"
        if in_kf and STALEY.search(l) and not re.search(r"as of|checked \d{4}|\d{4}-\d{2}-\d{2}", l, re.I):
            volatile.append(l.strip()[:80])
        if re.search(r"\d[\d,.]*\s*[km]?\s+views\b", l, re.I) and "as of" not in l:
            warns.append(f"view count without 'as of <date>': {l.strip()[:80]}")
        if l.startswith("## Sources") or l.startswith("source:"):
            continue
        defanged = QUOTED.sub("", l)  # drop quoted/backticked/parenthetical examples
        if INJECT.search(defanged):
            warns.append(
                "possible injected directive (confirm it's quoted/defanged, not a live "
                f"instruction copied from source): {l.strip()[:90]}"
            )

    fd = re.search(r"^fresh_days:\s*(\d+)", fm, re.M)
    if volatile and fd and int(fd.group(1)) > 30:
        fails.append(f"{len(volatile)} undated price/star line(s) need fresh_days <= 30 (or 'as of <date>' on the line), e.g.: {volatile[0]}")

    unmatched = []
    if not src.exists():
        fails.append(f"raw source missing: {src}")
    else:
        s = digits(src.read_text(encoding="utf-8", errors="replace"))
        kf = re.search(r"## Key findings\n(.*?)(?=\n## |\Z)", text, re.S)
        body = ISO_DATE.sub("", kf.group(1)) if kf else ""
        for m in sorted(set(NUM.findall(body))):
            core = digits(m.lstrip("~$").rstrip("%kKmM"))
            if len(core) < 2 or m.startswith("~"):
                continue  # single digits are noise; ~N is a rounded count
            if core not in s:
                unmatched.append(m)

    for f in fails:
        print("FAIL", f)
    for w in warns:
        print("WARN", w)
    if unmatched:
        print("UNMATCHED numbers (not literally in source; verifier must check):", ", ".join(unmatched))
    print("PRECHECK:", "FAIL" if fails else "OK")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
