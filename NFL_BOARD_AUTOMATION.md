# Automated pregame board refresh

**Built.** Product orchestration only. All 18 frozen production hashes are
unchanged, `PATH_C_STATE` and the capture/G0A workflows untouched.

Suite: **58 modules, 631 test functions, 3,466 checks, 0 failing, 0 raised.**

## Cadence

Two mechanisms, because one of them cannot fire yet and saying otherwise would
be the kind of silent absence this project keeps paying for.

| | schedule | state |
|---|---|---|
| `.github/workflows/nfl-product-board.yml` | `7,27,47 * * * *` | **inert until merged to `main`** |
| Routine `trig_01H9EQHMbCodyy8sFUyz4ukL` | hourly at `:41` | **live**, next 2026-09-10T17:41Z |

**GitHub runs scheduled workflows from the default branch only**, and `main`
does not yet carry the product layer. The workflow file is correct and will
begin firing on merge; until then it does nothing at all. The Routine covers
tonight — roughly seven more passes before the 00:35Z kickoff.

The Routine stores **no MCP connectors**, so its sessions run without
connector tools. That is fine here: the job is a local CLI plus a git push and
needs none. If it ever does, it must be recreated from a session holding them,
or from the claude.ai Routines UI.

**Twenty minutes buys nothing over an hour, and neither buys a board.** A pass
writes only when the stored input vintages actually change, so a tighter
schedule produces the same boards, not more of them.

## Every pass is one of four outcomes

| status | meaning | writes |
|---|---|---|
| `WRITTEN` | newer legitimate vintages existed | a new immutable board |
| `NO_NEW_INPUTS` | vintages byte-identical to the last board | nothing |
| `PAST_KICKOFF` | pregame is over | nothing |
| `REFUSED` / `ERROR` | the pipeline refused, with its own named code | nothing |

A pass that wrote nothing exits 0. A scheduler that treats `NO_NEW_INPUTS` as
a failure would page someone every hour for correct behaviour.

## Immutable storage and the index

```
nfl/product/boards/
  INDEX.jsonl                          append-only, one row per board ever written
  2026_01_SF_LA/
    LATEST.json                        a POINTER — holds nothing unique
    20260910T163449Z__bc8d60ac093c4a25/
      BOARD.md  board.json  forecast_artifact.json
      player_draws.npz.gz  player_draws_manifest.json  run_status.json
      PROTOCOL_RECORD.json  SEAL_SHA256.txt
```

The directory name carries **when** and **which run**, so two boards cannot
collide unless they are the same board. `store.write` raises `BoardExists`
rather than overwriting — a named refusal, so a caller cannot mistake it for an
ordinary failure and retry over the top.

`LATEST.json` is rebuildable from `INDEX.jsonl` at any time, and a test proves
it: losing the pointer costs convenience and nothing else. A mutable pointer
over an immutable set is safe; a mutable board would not be.

`PROTOCOL_RECORD.json` carries `written_at`, run id, every input vintage with
its hash and hours-before-kickoff, the draw digest, the component manifest, the
code commit, the authorization state, and the board it supersedes — with the
note that superseding never replaces.

## The five proofs

**1. Identical inputs + frozen model → identical draws.** The test reproduces a
stored board from its own `written_at` and compares every array. It also holds
in production: the orchestrated board and the manually sealed one earlier today
share **all 22 draw arrays bit-for-bit** and the same draw digest
`7f322318d10c55e1`, differing only in `written_at` and the `run_id` derived
from it. The run id embeds a `+dirty[n]` counter of uncommitted files, so the
test requires it to match only when the tree is clean, and says why.

**2. Only legitimately newer vintages alter a later board.** The fingerprint
covers each source's content hash **and** its observation time, so neither a
changed file nor a re-fetch of unchanged bytes passes unnoticed. Three
back-to-back passes agree and none writes. The live second pass returned
`NO_NEW_INPUTS`.

**3. Post-kickoff information cannot enter.** Kickoff is checked in `plan()`
and **again** between planning and execution, because a scheduler can fire at
the boundary. One second after kickoff, and kickoff itself, both refuse. Every
recorded vintage in the stored board is asserted to predate both kickoff and
`written_at`.

**4. SHADOW cannot masquerade as AUTHORIZED.** The label is derived from
`authorization.may_publish()` on every render — never carried in, defaulted, or
copied from a previous board. The test drives **both branches**, so the label
is proven a function of the gate rather than a constant that happens to be
right today. A stored board records the label it was written under, and the
board text carries it.

**5. Product failure cannot affect capture or G0A.** Isolation is structural,
not promised: the orchestrator's source is asserted to contain no reference to
`vintage_manifest`, `capture_vintage`, `gen_t90`, `PATH_C_STATE` or `.github`;
the store writes only under `nfl/product/boards/`; the workflow stages that one
path rather than `git add -A`; and its `concurrency` group is its own. The test
hashes every capture and governance file, runs a deliberately failing pass and
a normal one, and asserts nothing changed and nothing was deleted.

## A defect found while building this

`run()` caught `Exception`, and `SystemExit` is a `BaseException`. A single bad
game id therefore killed the whole scheduled pass, and **every later game in
the list was silently never checked** — the worst shape a failure can take in
an unattended job. Now caught deliberately, with the reason recorded at the
catch site, and `plan()` is contained too so `refresh` always answers with a
status.

## Tonight

1. Hourly passes generate a fresh SHADOW board whenever newer pregame inputs
   land. Each is preserved separately.
2. After the G0A adjudication: if NFL-1 becomes authorized, the next pass
   derives the new label from the gate and writes a **new** board. **No earlier
   SHADOW artifact is relabelled** — authorization is a property of when a
   forecast was written.
3. The last board written before kickoff is the frozen pre-kickoff board; every
   pass after that returns `PAST_KICKOFF`.
4. After the game, score that exact directory with
   `nfl/tools/score_game.py --forecast-dir <board_dir>`. Its seal is verified
   against `SEAL_SHA256.txt` before any outcome byte is read.

## Presentation standard preserved

Data freshness, status confidence, QB/RB/WR/TE distributions, P10/P25/P50/P75/
P90, TD probabilities, threshold probabilities, highest-confidence and
widest-uncertainty rankings, unavailable/provisional metrics, governance state.
The orchestrated board is byte-identical to the accepted format once hashes and
timestamps are normalised. Unsupported metrics remain `UNAVAILABLE` and are
never synthesized.
