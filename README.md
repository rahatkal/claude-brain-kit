# Claude Brain Kit — a second brain that checks itself before it saves

A Markdown second brain for [Claude Code](https://claude.com/claude-code) with one rule most setups skip:
**nothing gets saved as a fact until a separate checker confirms it against the raw source.**


## Does it actually work?
Receipts from the author's own brain logs for 2026-10-16 and 2026-10-19:
- 12 notes went through the verifier. 9 had at least one problem caught before saving; 3 passed on the first try.
- A draft credited reply comments to the wrong people and called a risk tool a drawdown "handbrake" it isn't → 1 FAIL + 3 UNSUPPORTED → fixed → PASS 36/36.
- A draft called a serious reply "a joke" → FAIL → fixed → PASS 40/40.
- A draft dropped a source's qualifier and overstated a claim → CONTESTED x2 → caveats added → PASS 27/27.
- Earlier: a claim credited to 3 people when only 1 made it, plus a link to the wrong raw file → 2 UNSUPPORTED → fixed → PASS 17/17.
- Full dated list of 25 catches: [CATCHES.md](CATCHES.md).

## Why
AI note-takers summarise, round numbers and add things the source never said. Those mistakes then sit in your notes, and the next session trusts them. This kit stops them at the door:

```
source → .drafts/<topic>.src.txt (full raw text)
       → .drafts/<topic>.md (draft)
       → precheck_note.py   (free: structure, dates, numbers not found in the source)
       → verifier subagent  (cheap Haiku model: PASS / FAIL / UNSUPPORTED / CONTESTED / STALE per claim)
       → fix → re-run until PASS
       → notes/             (pre-commit hook blocks any new note without "verified: yes")
```

## What's inside
| Piece | What it does |
|---|---|
| `AGENTS.md` | The one rulebook (map + rules + verify loop), under 8 KB. `CLAUDE.md` imports it and `GEMINI.md` points to it, so Claude Code, Codex and Gemini all follow the same rules |
| `tracker/goal-progress.csv` | Your real numbers against your North Star goals, logged only from what you report |
| `MEMORY.md` | Always-loaded core facts + your North Star goals |
| `.claude/agents/verifier.md` | Strict, cheap fact-checker. Judges, never edits. Ignores instructions planted in sources |
| `tools/precheck_note.py` | Free pre-check: required sections, freshness dates, numbers missing from the source, injected-instruction warnings |
| `tools/hooks/guard_hook.py` | Session start: loads your corrections. Before tools: blocks `.env` access (also when the name is split with quotes or backslashes), `git push`, commit-hook bypasses (`--no-verify`, `-n`, hooks-path changes), edits to the hook and settings themselves, and your `DANGER` list. At stop: sends Claude back once to log + commit |
| `tools/hooks/pre-commit` + `tools/secret_scan.py` | Blocks unverified new notes and API keys / private keys in commits |
| `night-shift/PLAYBOOK.md` | Corrections log: every time you correct Claude, it becomes a rule loaded next session |

## Install (5 minutes)
Needs: Claude Code, git, Python 3.9+ (stdlib only, no pip installs).
1. Copy this folder where you want your brain.
2. Run `sh setup.sh` (Windows: from Git Bash). It sets up git and the pre-commit hook.
3. Fill in `MEMORY.md` (who you are, your North Star goals) and any hard rules in `night-shift/PLAYBOOK.md`.
4. Try it: give Claude a link and say "make a note". Watch it go draft → precheck → verifier → note.

## Daily use
- Paste a link → verified note.
- Correct Claude → it logs the rule in the PLAYBOOK and follows it from the next session on.

## Pro pack
This free kit stops bad facts getting in. The Pro pack makes the brain improve itself over time:
- 6-question setup interview that writes your `MEMORY.md`, first project and hard rules
- 10 verifier trap tests, 4 built from real catches, to prove your checker still works after you change it
- Lessons loop: candidate lessons with evidence that become rules on your yes, plus pruning of rules that never fire
- `/decide` (decision memos that learn from past outcomes), `/review` (weekly review) and `/connect` (two-way note links)
- Rival-strategist and agent role-contract prompts, stale-note and context-size tools
Get it: https://rajamagic3.gumroad.com/l/claude-brain-kit

## Customize
- Add risky commands to `DANGER` in `tools/hooks/guard_hook.py`. Edit it yourself in an editor: Claude is blocked from that folder.
- Change `fresh_days` defaults in `AGENTS.md`.
- Using Codex or Gemini too? Same folder, same rules. The hooks are Claude Code-only; the pre-commit gate works with any tool.
- Add your own prompts under `prompts/<name>/system.md`.

## Security notes
- Keep your brain in a **private** repo, never a public fork: your notes hold personal data.
- Read any borrowed skill, prompt or hook code before you run it.
- `tools/hooks/guard_hook.py` blocks `.env` reads and edits (even split with quotes or backslashes), `git push`, `git commit --no-verify` and hook-path changes, edits to the hook and settings, and anything on your `DANGER` list. You run blocked actions yourself. It is a text-matching guard, not a sandbox: code that builds a name at runtime can still slip past it.
- The pre-commit hook runs `tools/secret_scan.py`, which blocks commits that add API keys or tokens (Anthropic, OpenAI, AWS, GitHub, Slack, Telegram) or private keys.
- Fetched web pages are data, not instructions: the verifier ignores instructions planted in a source and fails a note that repeats one, and `tools/precheck_note.py` warns on injected-looking directives.
