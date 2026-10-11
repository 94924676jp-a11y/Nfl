# Superseded results (kept, not deleted)

| File | Superseded by | Why |
|---|---|---|
| `REAL_CALL_REPLAY.json` "0 of 2,129 hook outputs differ" | `REAL_CALL_REPLAY_v2.json` and `nfl/tests/test_git_guard.py::test_12` | The replay loaded the base mode_guard from the scratchpad, so its `ROOT` was the scratchpad and every path resolved outside "the repository": the base guard could never deny, and the identity claim was vacuous. Found 2026-10-11 when a real call differed. Fixed in `replay_real_tool_calls.py` (`old.ROOT = new.ROOT`, asserted) and the replay now reports how many calls each guard denies. |
| `REAL_CALL_REPLAY_run1_before_fix.json` | `REAL_CALL_REPLAY_v2.json` | git_guard-1 before its false-positive fixes. |
| `FLOOR_GUARD_HISTORY_REPLAY*.json`, `FLOOR_GUARD_HELDOUT_HISTORY.json` | `FLOOR_GUARD_HELDOUT_301_480_v2.json` (fresh) and `_121_300_v2.json` | floor-guard-1. The 121-300 window has now been inspected once and is no longer untouched. |
| `coverage_review/*_1.json` | `coverage_review/*_2_IN_SAMPLE.json` | the first independent review measured version 1 held-out; version 2 was written against those fixtures, so its numbers on them are in-sample. |
