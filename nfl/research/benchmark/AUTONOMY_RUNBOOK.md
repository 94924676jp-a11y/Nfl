# AUTONOMY_RUNBOOK: always-on evaluation (mandate b0540a52 phase 6). A proposal; nothing activated.

**Status.** PROPOSED, awaiting the owner's approval of cadence and budget.

**Why agents cannot install it.** `.github/workflows/` is in `coordination/MODE_POLICY.json` `always_denied`. An agent
cannot add or schedule a workflow, and this runbook does not try to. The owner installs the file below, or tells an
agent with that permission to do so.

## What already runs (reused, not duplicated)

| workflow | trigger | role |
|---|---|---|
| `nfl-capture.yml` | every 30 min | permitted public captures into `nfl/vintage/` with manifest rows |
| `nfl-capture-liveness.yml` | hourly | capture freshness alarm |
| `nfl-availability.yml` | 06:17 and 18:17 UTC | participation-availability watch |
| `agent-orchestrator.yml` + heartbeat | push to coordination, `workflow_dispatch`, hourly heartbeat | one orchestrator per branch (concurrency), 45-min timeout; dispatches queue tasks |
| `nfl-production-forecast.yml` | dispatch only | built, NOT activated (NFL-1 not authorized) |

**Queues.** The engineering and research queues stay where they are (`coordination/ENGINEERING_QUEUE.json`,
`coordination/RESEARCH_QUEUE.json`). No new queue is created.

## Proposed new workflow: `nfl-evaluation.yml`

Three jobs, none publishing, none touching production.

| job | trigger | work | budget |
|---|---|---|---|
| `score-completed` | daily 07:13 UTC, plus dispatch | for every slate whose games are final in the newest capture and whose prelock artifacts exist: run `prospective_scorecard.py`, `four_arm.py` and `joint_calibration.py` (plus arm D = D2-ROLE once its prelock shadow exists), and append to `PROSPECTIVE_LEDGER.jsonl` (idempotent on slate id + forecast sha) | ≤ 15 min, 1 runner |
| `freshness` | daily 06:43 UTC | report capture clocks against slate kickoffs, RES-008..011 status and roster freshness (ELIG-D4) to the health file | ≤ 5 min |
| `challenger-weekly` | Tuesday 10:07 UTC, plus dispatch | run `reproduce.py` (every benchmark artifact must regenerate byte-identically; a mismatch is a red job), then each pre-registered challenger in its registered mode on the newest completed week only (prospective); never the holdout | ≤ 60 min, ≤ 1 runner |

**Idempotence and recovery.**
- **Run id:** `sha256(job, slate, forecast_sha, code_sha)`. A completed run id is skipped. A partial run writes nothing
  outside its own directory and is retried from its last finished stage, which is checkpointed by a content-addressed
  stage file.
- **Locks:** `concurrency: group: nfl-evaluation-${{ github.ref }}`, with `cancel-in-progress: false`.
- **Retries:** 2, with backoff of 5 then 20 minutes. A third failure opens an ENGINEERING_QUEUE item (`EVAL-FAIL-<run
  id>`) through the orchestrator's existing bridge. The workflow does not create GitHub issues itself.
- **Disk:** an archive is verified (`tar d`) before any delete. Caches are keyed by vintage and cutoff.
- **Alerting:** a red job, or a capture older than its freshness bound, appears in `nfl/research/benchmark/HEALTH.json`.
  The orchestrator's owner summary includes it.

**What it may never do.** Promote an arm; change a production default; upload an entry; spend money; subscribe to data;
read the 2025 holdout; tune on a scored prospective week.

## Cost

GitHub-hosted Ubuntu runners on this repository's plan.

| item | runner-minutes |
|---|---|
| daily jobs | about 20 per day |
| weekly challenger | up to 60 per week |
| total | about 200 per week |

An owner-set monthly cap can be enforced by a pre-step that reads the month's used minutes from the workflow-run API
and exits when over budget.

## Workflow text, for the owner to install

```yaml
name: NFL evaluation (scoring and challengers; never publishes)
on:
  schedule:
    - cron: '43 6 * * *'     # freshness
    - cron: '13 7 * * *'     # score completed slates
    - cron: '7 10 * * 2'     # weekly prospective challenger run
  workflow_dispatch:
    inputs:
      job: {required: true, default: 'score-completed'}
concurrency:
  group: nfl-evaluation-${{ github.ref }}
  cancel-in-progress: false
permissions:
  contents: write
jobs:
  evaluate:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
        with: {ref: claude/nfl-greenfield-architecture-stsxmk}
      - uses: actions/setup-python@v5
        with: {python-version: '3.12'}
      - run: pip install numpy
      - name: run
        run: python3.12 nfl/research/benchmark/eval_job.py "${{ github.event.inputs.job || 'auto' }}"
      - name: commit results only
        run: |
          git add nfl/research/benchmark/PROSPECTIVE_LEDGER.jsonl nfl/research/benchmark/HEALTH.json || true
          git -c user.name=nfl-eval -c user.email=eval@users.noreply.github.com commit -m "eval: ${{ github.run_id }}" || true
          git push || true
```

**Not built yet.** `eval_job.py` is the job dispatcher this file calls. Building it is ordinary research code, and is
the next queued engineering task once the owner approves the cadence.

## Owner decisions needed

1. Approve or adjust the cadence and the monthly runner-minute cap.
2. Install the workflow file. It is agent-denied.
3. Confirm which branch it runs on.
