# Second Brain — Map

Flat Markdown knowledge base. One topic per file. Answer from these files and cite the path. If the info isn't here, say so; don't guess.

Single rulebook for every AI tool: Claude Code (`CLAUDE.md` imports this file), Codex (reads `AGENTS.md`), Gemini (`GEMINI.md` points here). Not Claude Code? Read `MEMORY.md` first; hooks don't run for you, so follow the rules by hand, and for the verify step run `.claude/agents/verifier.md` as a prompt on a cheap model. Keep this file under 8 KB.

## Layout
- `tracker/goal-progress.csv` — one row per measurement of a North Star goal (`date,goal,metric,value,note`). Only numbers I report; never estimate or fill gaps.
- `notes/` — verified facts, one file per topic.
- `people/` — one card per person or company: who, context, meeting notes.
- `projects/` — one file per project: status, where paused, next steps.
- `MEMORY.md` — core long-term info + North Star goals (always loaded).
- `LEARNINGS.md` — lessons learned.
- `decisions.md` — dated log of choices and why; `## Outcomes` at the bottom records how they turned out.
- `prompts/` — reusable prompts, one folder each (`system.md`).
- `.drafts/` — raw sources (`<topic>.src.txt`) and unverified drafts.
- `night-shift/` — `PLAYBOOK.md` (rules learned from my corrections), `log/YYYY-MM-DD.md` (daily record).
- `tools/` — `precheck_note.py` (free structure/number check), `secret_scan.py` (pre-commit), `hooks/`.


## Rules
- Filenames: lowercase-hyphens, named for the topic (`tax-policy.md`). Never `note-12.md`.
- Before creating a file, check whether one already covers the topic; update it instead.
- New decision → append to `decisions.md` as `YYYY-MM-DD — decision — why`. Outcome known → append to `## Outcomes` (never edit the original line).
- Project files start with: `Status:`, `Last touched:`, `Next:`.
- Never store private keys, passwords, or API keys here (pre-commit `secret_scan.py` blocks them).
- Session start: the SessionStart hook injects the PLAYBOOK corrections log. Follow it.
- When I correct you: append `YYYY-MM-DD — correction — new rule` to the PLAYBOOK corrections log.
- Git: commit after each session (`git add -A && git commit -m "<what changed>"`). Before committing, append 3–6 fact lines to `night-shift/log/YYYY-MM-DD.md` (what changed, verifier FAILs, my corrections, `fired: <rule>` for each PLAYBOOK rule that changed what you did). The Stop hook reminds you.
- North Star: when a task connects to a goal in `MEMORY.md`, say so in one line. Don't force it.

## Verify BEFORE saving (the core loop)
1. Save the raw source text to `.drafts/<topic>.src.txt` — full text, never a summary (web pages via curl; PDFs/Office via markitdown).
2. Write the draft to `.drafts/<topic>.md`: `verified: pending`, `last_checked: YYYY-MM-DD`, `fresh_days: N` (30 prices/stars/models, 90 tools/repos, 365 papers/concepts) in the first lines; `## Key findings` first; `## Not checked` (what wasn't fetched/searched); `## Sources` last with URLs.
3. Run `python tools/precheck_note.py .drafts/<topic>.md` (free). Fix every FAIL.
4. Run the `verifier` subagent on the draft + src file, passing any UNMATCHED numbers. Statuses: PASS / FAIL / UNSUPPORTED / CONTESTED / STALE. Fix CONTESTED by adding the source's caveat, STALE by adding `as of <date>`, FAIL/UNSUPPORTED by fixing or dropping the claim. Re-run until `VERDICT: PASS` (max 3).
5. Only then set `verified: yes (verifier PASS n/n, date)`, move it into `notes/` and add it to the index below. The pre-commit hook blocks new notes without `verified: yes`.
6. If the new note contradicts or extends an older note, add a dated `## Updates` line to the old one citing `[[new-note]]`. Never rewrite old text.

## Always loaded
@MEMORY.md
(Other tools: read `MEMORY.md` yourself; only Claude Code expands `@` imports.)

## Notes index (`notes/`)
- (add one line per note: `topic-name` — what it covers)
