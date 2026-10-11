# Review 3 artifacts: what is held-out and what is not

- `REVIEW3_REPORT.md`, `task1_*_ca7a85af_HELD_OUT.json`, `helper_coverage_ca7a85af_HELD_OUT.json`: the reviewer's own
  output on commit ca7a85af, copied unmodified. These are the held-out measurements.
- `task2_*_RERUN_ON_FINAL_IN_SAMPLE.json`: the reviewer's Task 2 scripts write their results file when run. The
  author re-ran them on the fixed code at 01:41, after the report (01:28), so the original Task 2 raw results were
  overwritten. The held-out Task 2 numbers (git_guard 25/25 + 23/23, 0/15 + 0/7 false positives; floor_guard 12/12,
  1/8 false positives, supplementary X1-X6) survive only in `REVIEW3_REPORT.md`. The files here are in-sample.
- `r3_*_IN_SAMPLE.txt`: the same re-runs as printed.
