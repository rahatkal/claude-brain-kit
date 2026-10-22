# Catches: what the checker stopped from being saved

Real entries from the author's own brain logs (`night-shift/log/`, Oct 2026). Every research note goes through the verifier before it can be saved. These are the times the draft was wrong, what the checker said, and how it ended.

| Date | What the draft said | Verdict | Fixed to |
|---|---|---|---|
| 2026-10-04 | Reversed which model led a team of agents | FAIL | Flipped back to the source's order → 7/7 PASS |
| 2026-10-05 | Compared the 2025 OWASP list to 2021, which the source never did | 4 UNSUPPORTED | Comparison dropped → categories only, PASS |
| 2026-10-06 | Per-token price "40% cheaper" | FAIL: source says 20% (the 40% was from a different setting) | Corrected → PASS |
| 2026-10-07 | A blocked-access date that no source contained | FAIL | Dropped → 20/20 PASS |
| 2026-10-07 | Two price ranges for AI agent services, no source | FAIL x2 | Replaced with sourced figures → 5/5 PASS |
| 2026-10-07 | "Two weeks old" with no date | STALE | Added "as of 2026-09-28" → 20/20 PASS |
| 2026-10-08 | A licence claim about hosted services, not in the README | UNSUPPORTED | Dropped → 22/22 PASS |
| 2026-10-08 | "Needs LLM keys" (they're optional) | FAIL | Corrected |
| 2026-10-08 | Called a prompt pack "free"; the source never said so | UNSUPPORTED + 2 CONTESTED | Fixed → 22/22 PASS |
| 2026-10-08 | Summarised replies as "all agree", then as "jokes" | FAIL x2 | Third try matched the replies → 7/7 PASS |
| 2026-10-08 | A claim credited to 3 people when only 1 made it | UNSUPPORTED | Fixed → 17/17 PASS |
| 2026-10-08 | "12x" when the test said 12.2x; "paid" with no source | FAIL | Exact number, claim dropped → 36/36 PASS |
| 2026-10-08 | Added "parameters" as a unit the source didn't use | UNSUPPORTED | Removed → 17/17 PASS |
| 2026-10-09 | "55 lines" where the source said 55 replies | FAIL | Corrected → 17/17 PASS |
| 2026-10-09 | Said every paper beat a baseline "only modestly", the opposite of the sources | FAIL | 2 fix rounds → 38/38 PASS |
| 2026-10-09 | A fee of ~5% where the source said ~2% round-trip | FAIL + 12 UNSUPPORTED | Corrected; unfetched claims moved to "Not checked" |
| 2026-10-11 | "Unanswered questions" when only 40 of 128 replies were captured | UNSUPPORTED | Reworded → 16/16 PASS |
| 2026-10-12 | A reply "quoted" in paraphrase | FAIL | Real wording → PASS |
| 2026-10-12 | A usage limit without the source's hedge; "currently" with no date | CONTESTED + 2 STALE | Caveat and dates added |
| 2026-10-15 | Five takeaways that were the writer's own inferences, written as facts | 5 UNSUPPORTED | Labelled as inference |
| 2026-10-16 | Two repliers credited with one joke; only one made it | FAIL | Split → 36/36 PASS |
| 2026-10-16 | A size-capping script described as a drawdown "handbrake" | UNSUPPORTED | Rewritten to what the code does → 36/36 PASS |
| 2026-10-16 | A summary of replies that ignored "first page only" | CONTESTED | Limit stated → 25/25 PASS |
| 2026-10-19 | "Every job posting asks for years"; one of five didn't | FAIL | "4 of 5" → 36/36 PASS |
| 2026-10-19 | A sincere reply filed under "jokes" | FAIL | Moved → 40/40 PASS |

## The pattern
Most catches were not misread sources. They were words the writer added: "free", "paid", "only modestly", a unit, a third person. That is the mistake a summariser makes and a reader never notices. It's also the reason the checker reads the raw source, not a summary.

Across 60 notes logged by 2026-10-11, 35 (58%) hit at least one FAIL before passing.

## When the checker was wrong
It happens, and it's logged too: on 2026-10-04 it flagged examples as missing that a text search showed were in the source (fix: give the verifier exact search strings), and on 2026-10-08 it flagged a product claim that was in the source. A false alarm costs a minute; a wrong fact saved as true costs every later session that trusts it.

## Where this comes from
Each line is copied from a dated log entry, not written for this page. Set up the kit and your own `night-shift/log/` builds the same record for your notes.
