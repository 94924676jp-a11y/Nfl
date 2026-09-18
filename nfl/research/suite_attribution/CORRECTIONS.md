# Corrections to suite figures quoted in commit messages

Append-only. A commit message cannot be edited once pushed, and rewriting
history to fix a number is worse than the number. The artifacts are the record;
this file reconciles prose against them.

## 2026-09-18 — `dc7ceed` quotes the wrong run

The commit message of `dc7ceed` reads:

> 184 modules, 1997 functions, 10627 checks, 62 failing, 21 raised, 0
> zero-check, 23 blocked.

**Two of those figures are wrong.** They come from an earlier run
(`suite_disc2`) that was superseded before the commit. The log actually
committed as `suite_discovery.log`, and the diff committed as
`SUITE_DIFF_p9_discovery.json`, both say:

| | quoted in `dc7ceed` | actually committed |
|---|---|---|
| modules | 184 | 184 |
| test functions | 1997 | 1997 |
| checks | **10627** | **10632** |
| failing checks | **62** | **61** |
| raised | 21 | 21 |
| zero-check functions | 0 | 0 |
| blocked functions | 23 | 23 |

The difference is the final `test_discovery` revision, which added five checks
and resolved one failing check. **The conclusion the commit drew is unchanged
and was verified against the committed artifact**: NEWLY INTRODUCED none, three
resolved, against baseline `20468a5`.

Note that the generated state was never wrong. `SYSTEM_STATE.json` reads the
newest `SUITE_DIFF_*.json` rather than any prose, so `CURRENT_STATE.md` has
carried 10,632 and 61 throughout. Only the hand-written commit message drifted
— which is the same defect P7 was built to remove, appearing in the one place
P7 does not reach.
