"""Repair 5 -- migrate every sealed board off the old passing-credit function.

WHAT WAS WRONG
==============
`nfl/production/nonqb/shared_pass.py:172 credit_to_passers` split a team's
completions and passing touchdowns MULTINOMIALLY on the ATTEMPT share, and
split passing yards on that same attempt share independent of the completion
draw (`pyds_q = w * team_pyds`, line 189). A multinomial samples a finite pool
WITH replacement, so it can hand a quarterback more completions than he threw
attempts, more touchdowns than he threw completions, and passing yards in a
draw where he completed nothing. The team total closes exactly in every draw.
The per-quarterback split is not a box score.

`nfl/production/nonqb/football_engine.py:84 credit_passing_line` already
replaces it -- multivariate hypergeometric over `attempts - interceptions`,
then touchdowns over the credited completions, then yards on the COMPLETION
share -- and it asserts `cmp <= att`, `cmp <= att - int`, `ptd <= cmp` and
`cmp == 0 -> pyds == 0` on the values it is about to write, at lines 285-300.
Production has called it since the R9 rebuild. The defect that is left is
HISTORICAL: sealed boards built before that change carry the old output and
nothing marks them.

So this is a MIGRATION, not an invention. Nothing here re-implements a credit
scheme. The replacement function is imported and called.

WHAT THIS TOOL REBUILDS, AND WHAT IT DELIBERATELY DOES NOT
==========================================================
It rebuilds ONE STEP: the per-quarterback passing line, from the sealed
board's own stored inputs. Every array a migrated artifact carries that is not
`qb/cmp`, `qb/pyds` or `qb/ptd` is copied from the source unchanged.

It does NOT re-run the engine. A full re-run would need the slate feeds,
injury state and roster vintage as they stood before kickoff, and would not
reproduce the sealed draws even if they were present. Rebuilding the credit
step on the sealed inputs is the only rebuild that isolates the treatment.

It does NOT write `board.json` or `BOARD.md`. Those are a rendering --
per-player means, percentiles, thresholds and confidence scores -- produced by
code this workstream does not own. Emitting a second renderer's version would
be a second board renderer; copying the source's stale one would be worse. A
migrated artifact is therefore a DRAW artifact and says so, and what is owed
to make one consumable as a board is named in its `MIGRATION.json`.

WHAT THE INPUTS ARE, AND WHY THEY ARE RECOVERABLE
=================================================
`credit_passing_line` needs, per team-side: the per-quarterback attempt and
interception matrices, and the team's completions, passing yards and passing
touchdowns.

  * `qb/att` and `qb/int` are stored and were NEVER touched by the credit --
    it writes back only `cmp`, `pyds` and `ptd`. They are the original QB V1
    draws.
  * The team totals are the C3 identity itself: under C3 the team's passing
    line IS its receivers' line, so team completions are that side's
    `receiving/receptions` summed, team passing yards its
    `receiving/receiving_yards` summed, and team passing touchdowns its
    `receiving/receiving_td` summed. This tool derives them that way -- from
    the RECEIVING layer, which owns the event -- and then asserts they equal
    the stored per-quarterback sums in every draw, which is an independent
    second derivation of the same quantity.

RANDOMNESS, DECLARED
====================
The original engine stream cannot be recovered from a sealed artifact: the
credit rng is seeded once per game and its STATE at the credit call depends on
the whole preceding run. So this tool declares its own stream, derived from
the artifact's own identity and nothing else:

    seed = int(sha256(f'{SPEC_VERSION}|{source_run_id}|{team}')[:16], 16)

One stream per (source run, team side), so the result does not depend on the
order teams are iterated in, on the wall clock, or on how many boards were
migrated in the same process. Re-running this tool on the same input produces
the same values.

WHAT IT REFUSES
===============
`credit_passing_line` refuses a team-draw in which the receiving event caught
more passes than the quarterbacks had non-intercepted attempts to throw
(`PASSER_CREDIT_EXCEEDS_COMPLETABLE_ATTEMPTS`). That is an upstream coupling
gap between the targeted-throw budget and the interception draw; no per-passer
allocation can resolve it and it is not clipped here. A board carrying one is
reported UNMIGRATABLE, by name, with the draw index -- and is NOT written
half-migrated, because a board with one side rebuilt and one side not is
exactly the silently-partial artifact this repository keeps paying for.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import pickle
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.research import sealed_index as SI                          # noqa: E402
from nfl.production.nonqb import football_engine as FE               # noqa: E402

SPEC_VERSION = 'p4-passer-credit-migration-1'
REPLACEMENT = ('nfl.production.nonqb.football_engine.credit_passing_line '
               '(football_engine.py:84)')
SUPERSEDED = ('nfl.production.nonqb.shared_pass.credit_to_passers '
              '(shared_pass.py:172)')

# Migrated artifacts live OUTSIDE nfl/research/live/, deliberately.
#
# `live/` is the PROSPECTIVE namespace: every directory in it is a forecast
# sealed before a kickoff, and `sealed_index.live_draw_files()` is what the
# corpus fences and the prospective ledger read. A migrated artifact is a
# POST-HOC rebuild of a sealed artifact, built after the game it describes.
# Filing one under `live/` would put a post-hoc rebuild where a prospective
# forecast is counted -- the contamination this repository has already been
# bitten by once. They go in this workstream's own namespace and each one says
# in writing that it is inadmissible as prospective evidence.
MIGRATED_ROOT = _REPO / 'nfl' / 'research' / 'v4' / 'p4' / 'migrated'
LEDGER = _REPO / 'nfl' / 'research' / 'v4' / 'p4' / 'MIGRATION_LEDGER.json'

# The three metrics the credit owns. Everything else is copied unchanged.
CREDITED = ('qb__cmp', 'qb__pyds', 'qb__ptd')


# ------------------------------------------------------------------ loading


def corpus(include_replay=False):
    """Every sealed draw file, through the SHARED content-based discovery.

    `sealed_index.live_draw_files()` is the one entry point a corpus scan may
    use. A private glob here is how 17 boards stayed invisible to three fences
    at once; see `nfl/tests/test_sealed_corpus_census.py`.
    """
    if include_replay:
        return SI.live_draw_files(exclude=())
    return SI.live_draw_files()


def load(run_dir) -> Outcome:
    """Board, manifest and draws for one sealed run, or a NAMED refusal."""
    d = pathlib.Path(run_dir)
    board_p, man_p = d / 'board.json', d / 'player_draws_manifest.json'
    missing = [p.name for p in (board_p, man_p) if not p.exists()]
    z = SI.load_draws(d)
    if z is None:
        missing.append('player_draws.npz')
    if missing:
        return Outcome.blocked(
            'MIGRATION_RUN_INCOMPLETE',
            f'{d.name} is missing {missing}; refused rather than migrated '
            f'from a partial artifact.',
            cause=Cause.DATA, run_dir=str(d), missing=missing)
    board = json.loads(board_p.read_text())
    man = json.loads(man_p.read_text())
    if not (board.get('players') or []):
        return Outcome.blocked(
            'MIGRATION_RUN_EMPTY',
            f'{d.name} carries no player rows. An empty board is an error, '
            f'not a result.', cause=Cause.DATA, run_dir=str(d))
    arrays = {k: z[k] for k in z.files}
    if not arrays:
        return Outcome.blocked(
            'MIGRATION_DRAWS_EMPTY',
            f'{d.name} carries no draw matrices.', cause=Cause.DATA,
            run_dir=str(d))
    return Outcome.ok(
        'MIGRATION_RUN_LOADED',
        value={'dir': d, 'board': board, 'manifest': man, 'arrays': arrays},
        detail=f'{d.name}: {len(board["players"])} player row(s), '
               f'{len(arrays)} draw matrix(es)',
        n_players=len(board['players']), n_matrices=len(arrays))


def team_of(board):
    return {p['gsis_id']: p.get('team') for p in board.get('players') or []}


def sides(rec) -> Outcome:
    """Per-team row indices, resolved by gsis_id, never positionally."""
    tmap = team_of(rec['board'])
    layers = rec['manifest'].get('layers') or {}

    def ids(name):
        return (layers.get(name) or {}).get('row_ids') or []

    qb_ids, rec_ids, rush_ids = ids('qb'), ids('receiving'), ids('rushing')
    if not qb_ids:
        return Outcome.blocked(
            'MIGRATION_NO_QB_ROWS',
            f'{pathlib.Path(rec["dir"]).name} declares no qb row_ids, so no '
            f'passing line can be attributed.', cause=Cause.DATA)
    unknown = [g for g in qb_ids + rec_ids if tmap.get(g) is None]
    if unknown:
        return Outcome.fail(
            'MIGRATION_ROW_WITHOUT_TEAM',
            f'{len(unknown)} draw row(s) have no team in board.json; a side '
            f'cannot be formed and nothing is guessed.',
            n_unknown=len(unknown), examples=unknown[:5])
    teams = rec['board'].get('teams') or sorted(
        {v for v in tmap.values() if v})
    out = {t: {'qb': [i for i, g in enumerate(qb_ids) if tmap[g] == t],
               'receiving': [i for i, g in enumerate(rec_ids) if tmap[g] == t],
               'rushing': [i for i, g in enumerate(rush_ids)
                           if tmap.get(g) == t]}
           for t in teams}
    if not any(v['qb'] for v in out.values()):
        return Outcome.fail(
            'MIGRATION_NO_SIDE_HAS_A_QB',
            f'{pathlib.Path(rec["dir"]).name}: no team side owns a '
            f'quarterback row.')
    return Outcome.ok(
        'MIGRATION_SIDES', value=out, n_sides=len(out),
        detail=', '.join(f'{t}: {len(v["qb"])}qb/{len(v["receiving"])}recv'
                         for t, v in out.items()))


def team_totals(arrays, ri):
    """The team's passing line, from the RECEIVING layer that owns the event."""
    return {
        'cmp': arrays['receiving__receptions'][ri].sum(0).astype(float),
        'pyds': arrays['receiving__receiving_yards'][ri].sum(0).astype(float),
        'ptd': arrays['receiving__receiving_td'][ri].sum(0).astype(float),
    }


# ------------------------------------------------ which credit built a side


def side_credit(arrays, qi, ri) -> dict:
    """Which credit function produced this side's passing line.

    CONTENT-BASED AND EXACT, not a guess from a label or a commit date. The two
    schemes put the yardage on different shares, and both are deterministic
    given the stored inputs, so the stored `qb/pyds` reproduces one of them to
    the bit:

        old:  pyds_q = (att_q / sum att)  * team_pyds
        new:  pyds_q = (cmp_q / team_cmp) * team_pyds

    A side whose stored yardage matches neither is UNDETERMINED and is reported
    that way rather than assigned to whichever is closer.
    """
    if not ri:
        return {'credit': 'NO_RECEIVING_LAYER', 'd_old': None, 'd_new': None}
    A = arrays['qb__att'][qi].astype(float)
    C = arrays['qb__cmp'][qi].astype(float)
    Y = arrays['qb__pyds'][qi].astype(float)
    tt = team_totals(arrays, ri)
    tot = A.sum(0)
    w = np.where(tot > 0, A / np.where(tot > 0, tot, 1.0),
                 1.0 / max(len(qi), 1))
    old = w * tt['pyds'][None, :]
    den = np.where(tt['cmp'] > 0, tt['cmp'], 1.0)
    new = np.where(tt['cmp'][None, :] > 0,
                   C / den[None, :] * tt['pyds'][None, :], 0.0)
    d_old = float(np.abs(Y - old).max()) if Y.size else 0.0
    d_new = float(np.abs(Y - new).max()) if Y.size else 0.0
    if d_old <= 1e-9 and d_new > 1e-9:
        k = 'OLD'
    elif d_new <= 1e-9 and d_old > 1e-9:
        k = 'NEW'
    elif d_old <= 1e-9 and d_new <= 1e-9:
        k = 'INDISTINGUISHABLE'
    else:
        k = 'UNDETERMINED'
    return {'credit': k, 'd_old': d_old, 'd_new': d_new}


def board_family(arrays, side_map) -> dict:
    """QB_ONLY / C3_OLD_CREDIT / C3_NEW_CREDIT / C3_UNDETERMINED."""
    per = {t: side_credit(arrays, v['qb'], v['receiving'])
           for t, v in side_map.items() if v['qb']}
    kinds = {v['credit'] for v in per.values()}
    if kinds <= {'NO_RECEIVING_LAYER'}:
        fam = 'QB_ONLY'
    elif 'UNDETERMINED' in kinds:
        fam = 'C3_UNDETERMINED'
    elif 'OLD' in kinds:
        fam = 'C3_OLD_CREDIT'
    elif kinds & {'NEW', 'INDISTINGUISHABLE'}:
        fam = 'C3_NEW_CREDIT'
    else:
        fam = 'C3_UNDETERMINED'
    return {'family': fam, 'sides': per}


# ------------------------------------------------------- coherence scanning


COHERENCE_CHECKS = (
    ('cmp_within_att', 'cmp <= att',
     'a completion is an attempt that was caught, so a passer cannot complete '
     'more passes than he threw'),
    ('cmp_plus_int_within_att', 'cmp + int <= att',
     'an interception is an incompletion, so completions and interceptions '
     'are disjoint subsets of the attempts'),
    ('ptd_within_cmp', 'ptd <= cmp',
     'a touchdown pass is a completion'),
    ('ptd_within_att', 'ptd <= att',
     'implied by the two above, counted separately because it reaches cells '
     'they do not'),
    ('zero_cmp_zero_pyds', 'cmp == 0 -> pyds == 0',
     'passing yards accrue on catches; with no catch there is nothing for '
     'them to accrue on'),
    ('rushing_td_within_carries', 'rushing_td <= carries',
     'a rushing touchdown is a carry that reached the end zone'),
)
CHECK_NAMES = tuple(c[0] for c in COHERENCE_CHECKS)


def coherence(arrays) -> Outcome:
    """Per-row box-score coherence over one board's stored draws.

    A SCAN OVER ZERO CELLS IS NOT A PASSING SCAN. The cell counts come back
    with the violations and the caller is expected to assert both.
    """
    need = ('qb__att', 'qb__cmp', 'qb__int', 'qb__ptd', 'qb__pyds')
    absent = [k for k in need if k not in arrays]
    if absent:
        return Outcome.blocked(
            'COHERENCE_QB_METRICS_ABSENT',
            f'the draw artifact carries no {absent}; the coherence of a '
            f'passing line cannot be measured without them.',
            cause=Cause.DATA, absent=absent)
    A = arrays['qb__att'].astype(np.int64)
    I = arrays['qb__int'].astype(np.int64)
    C = arrays['qb__cmp'].astype(np.int64)
    P = arrays['qb__ptd'].astype(np.int64)
    Y = arrays['qb__pyds'].astype(float)
    if A.size == 0:
        return Outcome.blocked(
            'COHERENCE_NO_QB_CELLS',
            'the qb layer holds zero cells; a scan that measured nothing is '
            'not a scan that passed.', cause=Cause.DATA)
    v = {'cmp_within_att': int((C > A).sum()),
         'cmp_plus_int_within_att': int((C + I > A).sum()),
         'ptd_within_cmp': int((P > C).sum()),
         'ptd_within_att': int((P > A).sum()),
         'zero_cmp_zero_pyds': int(((C == 0) & (np.abs(Y) > 1e-9)).sum())}
    qb_any = ((C > A) | (C + I > A) | (P > C) | (P > A)
              | ((C == 0) & (np.abs(Y) > 1e-9)))
    cells = {'qb': int(A.size), 'rushing': 0}
    if 'rushing__carries' in arrays and 'rushing__rushing_td' in arrays:
        RC = arrays['rushing__carries'].astype(float)
        RT = arrays['rushing__rushing_td'].astype(float)
        v['rushing_td_within_carries'] = int((RT > RC + 1e-9).sum())
        cells['rushing'] = int(RC.size)
    else:
        v['rushing_td_within_carries'] = 0
    return Outcome.ok(
        'COHERENCE_SCANNED',
        value={'violations': v, 'cells': cells,
               'distinct_qb_cells': int(qb_any.sum()),
               'total': int(sum(v.values()))},
        detail=f'{sum(v.values())} violation(s) over {A.size} qb cell(s) and '
               f'{cells["rushing"]} rushing cell(s)',
        n_qb_cells=int(A.size), n_violations=int(sum(v.values())))


# ------------------------------------------------------ the upper-tail bound


# The all-time NFL single-game passing record. A PUBLISHED EXTERNAL FACT, not a
# constant fitted here: Norm Van Brocklin, Los Angeles Rams at New York Yanks,
# 1951-09-28, 554 yards. It is already quoted in this repository at
# nfl/research/v3/x1/X1_DRAW_PATHOLOGY_CENSUS.md section 3.7 and
# nfl/research/v3/AUTOPSY_DEN_KC.md section 5.5.
SINGLE_GAME_PASSING_RECORD = 554.0
RECORD_SOURCE = ('all-time NFL single-game passing record -- Norm Van '
                 'Brocklin, LA Rams at NY Yanks, 1951-09-28. Published '
                 'external fact; quoted in X1_DRAW_PATHOLOGY_CENSUS.md 3.7.')
QB_HISTORY = _REPO / 'nfl' / 'research' / 'qb2' / 'qb.pkl'


def historical_tail_bound() -> Outcome:
    """The upper-tail bound, DERIVED, with the derivation attached.

    WHY NOT A ROUND NUMBER, AND WHY NOT THE RECORD ITSELF. 554 is one
    realisation, not a bound. A Monte Carlo engine that can never exceed the
    all-time record is wrong in the other direction: some probability mass
    above it is correct, and a fence forbidding any would be a clip in a
    fence's clothing. So the bound is on the RATE, not on any single draw.

    THE DERIVATION, in full.

      1. The estimation corpus is every quarterback game-line in
         `nfl/research/qb2/qb.pkl` with at least one completion -- the same
         rows `qb2_lib.pools` resamples yards-per-completion from, so it is
         the generator's own donor pool and not an outside yardstick.
      2. Count how many of those realised games exceeded the record. The
         answer is expected to be zero, and the observed maximum comes back
         with it so the margin is visible.
      3. Zero events in n trials does not mean the probability is zero. The
         rule of three gives the exact one-sided 95% upper confidence limit,
         p_max = 1 - 0.05 ** (1 / n), which at this n is about 3 / n.
      4. The fence is then: the share of SIMULATED quarterback game-lines
         exceeding the record must not exceed p_max. A corpus above it is
         emitting record-breaking games at a rate the realised record rules
         out at 95% confidence.

    A SECOND, HARDER BOUND COMES BACK ALONGSIDE IT. A completed forward pass
    gains at most 99 yards -- the line of scrimmage sits at most on a 1-yard
    line and the play ends between the goal lines -- so a game total cannot
    exceed 99 * completions in absolute value. That one is a rule of the game
    rather than a statistic, and it is the only bound that holds
    unconditionally.

    NEITHER BOUND CLIPS ANYTHING. Both are measured on the draws as they are.
    """
    if not QB_HISTORY.exists():
        return Outcome.blocked(
            'TAIL_BOUND_NOT_DERIVABLE',
            f'{QB_HISTORY} is absent, so the exceedance rate has no empirical '
            f'anchor and the bound is refused rather than assumed.',
            cause=Cause.DATA, wanted=str(QB_HISTORY))
    with open(QB_HISTORY, 'rb') as fh:
        d = pickle.load(fh)
    rows = list((d.get('player') or {}).values())
    py = np.array([float(r.get('pass_yards', 0.0)) for r in rows])
    cm = np.array([int(r.get('completions', 0)) for r in rows])
    keep = cm > 0
    n = int(keep.sum())
    if n < 500:
        return Outcome.blocked(
            'TAIL_BOUND_SAMPLE_TOO_SMALL',
            f'only {n} realised quarterback game-line(s) with a completion; a '
            f'95% rule-of-three limit on that is not a bound worth asserting.',
            cause=Cause.DATA, n=n)
    obs_max = float(py[keep].max())
    exceed = int((py[keep] > SINGLE_GAME_PASSING_RECORD).sum())
    if exceed:
        return Outcome.fail(
            'TAIL_BOUND_RECORD_EXCEEDED_IN_HISTORY',
            f'{exceed} realised game(s) in the estimation corpus exceed '
            f'{SINGLE_GAME_PASSING_RECORD:.0f} yards, so the record quoted '
            f'here is not the record. The bound is refused rather than derived '
            f'from a wrong anchor.', n_exceed=exceed, n=n)
    p_max = float(1.0 - 0.05 ** (1.0 / n))
    return Outcome.ok(
        'TAIL_BOUND_DERIVED',
        value={'record': SINGLE_GAME_PASSING_RECORD, 'n_history': n,
               'observed_max': obs_max, 'exceedances_in_history': exceed,
               'max_exceedance_rate': p_max, 'rule_of_three_approx': 3.0 / n,
               'hard_rule_bound': 'abs(pyds) <= 99 * cmp'},
        detail=f'{n} realised QB game-lines, max {obs_max:.0f} yards, '
               f'{exceed} above {SINGLE_GAME_PASSING_RECORD:.0f}; 95% '
               f'one-sided limit on the exceedance rate {p_max:.3e}',
        source=str(QB_HISTORY.relative_to(_REPO)),
        record_source=RECORD_SOURCE,
        derivation='rule of three on zero exceedances: 1 - 0.05**(1/n)')


def tail_scan(arrays, side_map) -> Outcome:
    """Record exceedances and hard-rule violations, split by side family.

    Split by SIDE, not by board, because the two generators are different: a
    side with a receiving layer gets its passing yards from the receiving
    event; a side without one gets them from `qb2_lib`'s
    yards-per-completion resample.
    """
    if 'qb__pyds' not in arrays or 'qb__cmp' not in arrays:
        return Outcome.blocked('TAIL_SCAN_METRICS_ABSENT',
                               'no qb/pyds to scan', cause=Cause.DATA)
    Y = arrays['qb__pyds'].astype(float)
    C = arrays['qb__cmp'].astype(np.int64)
    if Y.size == 0:
        return Outcome.blocked('TAIL_SCAN_NO_CELLS',
                               'the qb layer holds zero cells',
                               cause=Cause.DATA)
    out = {}
    for t, v in side_map.items():
        qi = v['qb']
        if not qi:
            continue
        fam = 'C3_SIDE' if v['receiving'] else 'QB_ONLY_SIDE'
        y, c = Y[qi], C[qi]
        b = out.setdefault(fam, {'cells': 0, 'above_record': 0,
                                 'above_99_per_cmp': 0, 'max': 0.0})
        b['cells'] += int(y.size)
        b['above_record'] += int((y > SINGLE_GAME_PASSING_RECORD).sum())
        b['above_99_per_cmp'] += int((np.abs(y) > 99.0 * c + 1e-9).sum())
        b['max'] = max(b['max'], float(y.max()))
    if not out:
        return Outcome.blocked('TAIL_SCAN_NO_SIDES',
                               'no team side owns a quarterback row',
                               cause=Cause.DATA)
    return Outcome.ok(
        'TAIL_SCANNED', value=out,
        detail='; '.join(f'{k}: {v["above_record"]}/{v["cells"]} above the '
                         f'record, max {v["max"]:.0f}'
                         for k, v in sorted(out.items())))


# ----------------------------------------------------------------- migration


def _stream_seed(source_run_id, team):
    key = f'{SPEC_VERSION}|{source_run_id}|{team}'
    return int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)


def _file_sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _rel_or_abs(p):
    """Repo-relative when it is inside the repo, absolute when it is not.

    The seal-preservation proof runs the whole migration into a temporary root
    outside the repository, and a ledger line is not worth crashing over.
    """
    p = pathlib.Path(p)
    try:
        return str(p.resolve().relative_to(_REPO))
    except ValueError:
        return str(p)


def seal_snapshot(include_replay=True):
    """sha256 of EVERY file in EVERY sealed run directory.

    Taken before and after a migration and compared. This is how "the seals
    were preserved byte-identical" becomes a measurement rather than an
    intention: the migration never opens a source directory for writing, and
    this proves it on the bytes rather than on the code path.
    """
    out = {}
    for f in corpus(include_replay=include_replay):
        for p in sorted(f.parent.rglob('*')):
            if p.is_file():
                out[str(p.resolve().relative_to(_REPO))] = _file_sha(p)
    return out


def effective_corpus(ledger=None, include_replay=True) -> Outcome:
    """What a consumer should scan AFTER the migration, and why.

    One entry per sealed source board, each carrying the directory that now
    represents it:

        MIGRATED        the rebuilt artifact supersedes the source. The source
                        stays on disk, byte-identical, as the historical
                        record; it is superseded, not deleted, and the pointer
                        is here rather than in the sealed directory because
                        nothing may be written into one.
        UNCHANGED       no old-credit side; the source IS the current artifact.
        UNMIGRATABLE    the replacement refused these inputs by name. DECLARED,
                        never silently dropped -- a consumer that scans the
                        corpus must see it and decide.

    A board on disk that is in none of these is a discovery gap, and the caller
    is expected to assert that the set matches `corpus()`.
    """
    p = pathlib.Path(ledger or LEDGER)
    if not p.exists():
        # NO LEDGER MEANS NO MIGRATION HAS BEEN RECORDED, AND THE EFFECTIVE
        # CORPUS IS THEN THE SEALED CORPUS EXACTLY AS BUILT. It is deliberately
        # not a refusal: this is the pre-migration state, and a fence over it
        # has to FAIL on the old-credit boards rather than go quiet. A fence
        # that reports "cannot evaluate" when the artifact it depends on is
        # missing is how a defect stops being visible.
        rows = [{'source': str(f.parent.resolve().relative_to(_REPO)),
                 'scan': str(f.parent.resolve().relative_to(_REPO)),
                 'status': 'UNCHANGED', 'code': 'NO_MIGRATION_RECORDED'}
                for f in corpus(include_replay=include_replay)]
        if not rows:
            return Outcome.blocked(
                'EFFECTIVE_CORPUS_EMPTY',
                'no ledger and no boards on disk.', cause=Cause.DATA)
        return Outcome.ok(
            'EFFECTIVE_CORPUS_PRE_MIGRATION', value=rows,
            detail=f'{len(rows)} board(s), none migrated: {p} does not exist, '
                   f'so the effective corpus is the sealed corpus as built',
            MIGRATED=0, UNCHANGED=len(rows), UNMIGRATABLE=0,
            ledger_present=False)
    doc = json.loads(p.read_text())
    entries = doc.get('entries') or []
    if not entries:
        return Outcome.fail(
            'EFFECTIVE_CORPUS_LEDGER_EMPTY',
            f'{p} records no boards. An empty ledger is an error, not a '
            f'result.')
    by_src = {e['source']: e for e in entries}
    out = []
    for f in corpus(include_replay=include_replay):
        rel = str(f.parent.resolve().relative_to(_REPO))
        e = by_src.get(rel)
        if e is None:
            return Outcome.fail(
                'EFFECTIVE_CORPUS_BOARD_NOT_IN_LEDGER',
                f'{rel} is on disk and the migration ledger does not mention '
                f'it. A board the migration never saw is a discovery gap, not '
                f'a clean board.', board=rel)
        if e['status'] == 'MIGRATED':
            out.append({'source': rel, 'scan': e['dest'], 'status': 'MIGRATED',
                        'migrated_run_id': e.get('migrated_run_id')})
        elif e['status'] == 'UNMIGRATABLE':
            out.append({'source': rel, 'scan': rel, 'status': 'UNMIGRATABLE',
                        'code': e.get('code'), 'refusals': e.get('refusals')})
        else:
            out.append({'source': rel, 'scan': rel, 'status': 'UNCHANGED',
                        'code': e.get('code')})
    n = {k: sum(1 for r in out if r['status'] == k)
         for k in ('MIGRATED', 'UNCHANGED', 'UNMIGRATABLE')}
    return Outcome.ok(
        'EFFECTIVE_CORPUS', value=out,
        detail=f'{len(out)} board(s): {n["MIGRATED"]} migrated, '
               f'{n["UNCHANGED"]} unchanged, {n["UNMIGRATABLE"]} unmigratable',
        ledger_present=True, **n)


def side_map_from(d) -> Outcome:
    """Per-team row indices for ANY artifact -- sealed board or migrated one.

    A sealed board carries the gsis_id -> team map in `board.json`; a migrated
    artifact carries the same map in `MIGRATION.json` `row_identity`, copied
    from its source. Reading them through one function is what stops a scan
    from silently covering only the shape it happens to know.
    """
    d = pathlib.Path(d)
    mig = d / 'MIGRATION.json'
    if mig.exists():
        ri = (json.loads(mig.read_text()).get('row_identity') or {})
        if not ri.get('qb'):
            return Outcome.fail(
                'SIDE_MAP_MIGRATED_ARTIFACT_HAS_NO_QB_ROWS',
                f'{d.name}/MIGRATION.json carries no qb row identity.')
        teams = sorted({t for lay in ri.values() for t in lay['teams'] if t})
        return Outcome.ok(
            'SIDE_MAP',
            value={t: {lay: [i for i, x in
                             enumerate((ri.get(lay) or {}).get('teams') or [])
                             if x == t]
                       for lay in ('qb', 'receiving', 'rushing')}
                   for t in teams},
            n_sides=len(teams), source='MIGRATION.json')
    lo = load(d)
    if lo.state is not State.PASS:
        return lo
    return sides(lo.value)


def arrays_at(d) -> Outcome:
    """The draw matrices for a directory, migrated artifact or sealed board."""
    z = SI.load_draws(pathlib.Path(d))
    if z is None:
        return Outcome.blocked(
            'DRAWS_ABSENT', f'{d} holds no player_draws.npz[.gz]',
            cause=Cause.DATA, run_dir=str(d))
    a = {k: z[k] for k in z.files}
    if not a:
        return Outcome.blocked('DRAWS_EMPTY', f'{d} holds no draw matrices',
                               cause=Cause.DATA, run_dir=str(d))
    return Outcome.ok('DRAWS_LOADED', value=a, n_matrices=len(a))


def _sha_array(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def _row_identity(rec):
    tmap = team_of(rec['board'])
    out = {}
    for lay, spec in (rec['manifest'].get('layers') or {}).items():
        spec = spec or {}
        if spec.get('row_axis') != 'gsis_id':
            continue
        ids = spec.get('row_ids') or []
        out[lay] = {'row_ids': ids, 'teams': [tmap.get(g) for g in ids]}
    return out


def migrate(run_dir, out_root=None, write=True) -> Outcome:
    """Rebuild ONE sealed board's passing line through the replacement.

    PASS with the migrated arrays; NOT_APPLICABLE for a board no old credit
    touched; FAIL or BLOCKED naming exactly what refused.
    """
    out_root = pathlib.Path(out_root or MIGRATED_ROOT)
    lo = load(run_dir)
    if lo.state is not State.PASS:
        return lo
    rec = lo.value
    so = sides(rec)
    if so.state is not State.PASS:
        return so
    side_map, arrays = so.value, rec['arrays']
    fam = board_family(arrays, side_map)
    before = coherence(arrays)
    if before.state is not State.PASS:
        return before
    src = pathlib.Path(rec['dir'])
    src_rel = str(src.resolve().relative_to(_REPO))
    src_run = rec['board'].get('run_id') or src.name

    if fam['family'] != 'C3_OLD_CREDIT':
        return Outcome.not_applicable(
            'MIGRATION_NOT_NEEDED',
            f'{src.name} is {fam["family"]}: no team side carries a passing '
            f'line built by the superseded credit, so there is nothing to '
            f'migrate.',
            family=fam['family'], source=src_rel,
            side_credit={t: v['credit'] for t, v in fam['sides'].items()},
            violations_before=before.value['violations'])

    # ONE PASS TO DECIDE, THEN ONE PASS TO WRITE. Every side is credited before
    # anything is kept, so a board that refuses on its second side is never
    # written with its first side already rebuilt.
    new = {k: np.array(arrays[k], copy=True) for k in CREDITED}
    per_side, refusals = {}, []
    for t, v in side_map.items():
        qi, ri = v['qb'], v['receiving']
        if not qi:
            continue
        if not ri:
            per_side[t] = {'action': 'UNTOUCHED',
                           'why': 'no receiving layer on this side, so the '
                                  'credit never ran and the passing line is '
                                  'the raw QB V1 draw'}
            continue
        A = arrays['qb__att'][qi].astype(float)
        I = arrays['qb__int'][qi].astype(float)
        tt = team_totals(arrays, ri)
        # SECOND, INDEPENDENT DERIVATION OF THE SAME TEAM TOTAL. The receiving
        # layer owns the event; the stored per-quarterback sums are what the
        # old credit wrote. They must agree in every draw. If they do not,
        # these are not the inputs the credit was given and nothing is rebuilt
        # from a guess.
        mism = {}
        for name, key in (('cmp', 'qb__cmp'), ('pyds', 'qb__pyds'),
                          ('ptd', 'qb__ptd')):
            bad = int((np.abs(arrays[key][qi].astype(float).sum(0)
                              - tt[name]) > 1e-6).sum())
            if bad:
                mism[name] = bad
        if mism:
            refusals.append((t, 'MIGRATION_TEAM_TOTAL_DOES_NOT_RECONCILE',
                             f'{mism} draw(s) where the stored per-passer sum '
                             f'differs from the receiving-layer total'))
            per_side[t] = {'action': 'REFUSED',
                           'code': 'MIGRATION_TEAM_TOTAL_DOES_NOT_RECONCILE',
                           'detail': mism}
            continue
        rng = np.random.default_rng(_stream_seed(src_run, t))
        cr = FE.credit_passing_line(A, I, tt['cmp'], tt['pyds'], tt['ptd'], rng)
        if cr.state is not State.PASS:
            ev = cr.evidence or {}
            refusals.append((t, cr.code, cr.detail[:400]))
            per_side[t] = {'action': 'REFUSED', 'code': cr.code,
                           'detail': cr.detail[:400],
                           'evidence': {k: ev[k] for k in
                                        ('n_bad', 'worst_draw',
                                         'worst_shortfall') if k in ev}}
            continue
        for key, name in (('qb__cmp', 'cmp'), ('qb__pyds', 'pyds'),
                          ('qb__ptd', 'ptd')):
            val = np.asarray(cr.value[name])
            new[key][qi] = (val.astype(arrays[key].dtype)
                            if arrays[key].dtype.kind in 'iu' else val)
        shift = float(np.abs(new['qb__cmp'][qi].astype(float)
                             - arrays['qb__cmp'][qi].astype(float)).mean())
        per_side[t] = {'action': 'MIGRATED', 'n_qb_rows': len(qi),
                       'n_recv_rows': len(ri),
                       'stream_seed': _stream_seed(src_run, t),
                       'mean_abs_completion_shift': round(shift, 6),
                       'scheme': (cr.evidence or {}).get('scheme')}

    if refusals:
        return Outcome.fail(
            'MIGRATION_REFUSED',
            f'{src.name}: {len(refusals)} team side(s) refused by the '
            f'replacement credit function -- '
            + '; '.join(f'{t}: {c}' for t, c, _ in refusals)
            + '. The board is NOT written half-migrated.',
            source=src_rel, source_run_id=src_run, family=fam['family'],
            per_side=per_side,
            refusals=[{'team': t, 'code': c, 'detail': d}
                      for t, c, d in refusals],
            violations_before=before.value['violations'])

    migrated = dict(arrays)
    migrated.update(new)
    after = coherence(migrated)
    if after.state is not State.PASS:
        return after
    tail = tail_scan(migrated, side_map)
    run_id = hashlib.sha256('|'.join(
        [SPEC_VERSION, src_rel, src_run]
        + [f'{k}:{_sha_array(new[k])}' for k in CREDITED]
    ).encode()).hexdigest()[:16]
    game_id = rec['board'].get('game_id') or SI.game_id_of(src)
    dest = out_root / str(game_id) / src.parent.name / run_id

    doc = {
        'spec_version': SPEC_VERSION,
        'what_this_is': (
            "a POST-HOC rebuild of one sealed board's per-quarterback passing "
            'line through the replacement credit function. It is NOT a '
            'prospective forecast, it was built after the game it describes, '
            'and it is inadmissible as prospective evidence.'),
        'not_a_board': (
            'board.json and BOARD.md are deliberately NOT regenerated. Their '
            'per-player means, percentiles, thresholds and confidence scores '
            'are a rendering produced by code this workstream does not own; a '
            'second renderer would be a second board and a copied stale one '
            'would be worse. Owed, to make this consumable as a board: run '
            'the existing board renderer over these draws.'),
        'source': {'dir': src_rel, 'run_id': src_run, 'game_id': str(game_id),
                   'model_configuration':
                       rec['board'].get('model_configuration'),
                   'code_commit': rec['board'].get('code_commit'),
                   'draw_content_digest':
                       rec['board'].get('draw_content_digest'),
                   'draws_sha256': rec['board'].get('draws_sha256'),
                   'draws_file_sha256_on_disk': _file_sha(
                       src / ('player_draws.npz'
                              if (src / 'player_draws.npz').exists()
                              else 'player_draws.npz.gz')),
                   'seal_preserved': ('byte-identical; nothing was written '
                                      'into the source directory')},
        'migrated_run_id': run_id,
        'credit': {
            'superseded': SUPERSEDED, 'replacement': REPLACEMENT,
            'scheme': ('multivariate hypergeometric over (attempts - '
                       'interceptions), then over the credited completions; '
                       'yards on the COMPLETION share'),
            'coherent_by_construction': ['cmp <= att', 'cmp <= att - int',
                                         'ptd <= cmp',
                                         'cmp == 0 -> pyds == 0'],
            'metrics_rewritten': list(CREDITED),
            'metrics_copied_unchanged': sorted(k for k in arrays
                                               if k not in CREDITED)},
        'randomness': {
            'stream': 'numpy default_rng(seed), one per (source run, team)',
            'seed_derivation':
                "int(sha256('{SPEC_VERSION}|{source_run_id}|{team}')[:16], 16)",
            'why_not_the_original_stream': (
                'the engine seeds the credit rng once per game and its STATE '
                'at the credit call depends on the whole preceding run, which '
                'a sealed artifact does not carry. A stream derived from the '
                "artifact's own identity is reproducible; a re-created engine "
                'stream would be a guess wearing provenance.')},
        'team_totals_source': (
            'the receiving layer of the same side -- receptions, '
            'receiving_yards and receiving_td summed -- cross-checked against '
            'the stored per-quarterback sums in every draw'),
        'sides': per_side,
        'family_before': fam['family'],
        'coherence_before': before.value['violations'],
        'coherence_after': after.value['violations'],
        'cells': after.value['cells'],
        'upper_tail_after': tail.value if tail.state is State.PASS else None,
        'row_identity': _row_identity(rec),
    }

    if write:
        dest.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(dest / 'player_draws.npz', **migrated)
        man = json.loads(json.dumps(rec['manifest']))
        for k in CREDITED:
            key = k.replace('__', '/')
            if key in (man.get('arrays') or {}):
                man['arrays'][key]['sha256'] = _sha_array(migrated[k])
        man['run_id'] = run_id
        man['migrated_from_run_id'] = src_run
        man['content_digest'] = hashlib.sha256('|'.join(
            f'{k}:{man["arrays"][k]["sha256"]}'
            for k in sorted(man.get('arrays') or {})).encode()).hexdigest()
        (dest / 'player_draws_manifest.json').write_text(
            json.dumps(man, indent=1, sort_keys=True) + '\n')
        (dest / 'MIGRATION.json').write_text(
            json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n')

    n_mig = sum(1 for v in per_side.values() if v['action'] == 'MIGRATED')
    return Outcome.ok(
        'MIGRATED',
        value={'dest': dest, 'doc': doc, 'arrays': migrated, 'run_id': run_id,
               'written': bool(write), 'side_map': side_map},
        detail=f'{src.name} -> {run_id}: {n_mig} side(s) rebuilt, '
               f'{before.value["total"]} -> {after.value["total"]} violation(s)',
        source=src_rel, violations_before=before.value['total'],
        violations_after=after.value['total'])


def run(include_replay=True, out_root=None, write=True) -> Outcome:
    """Migrate the whole corpus and return one ledger."""
    files = corpus(include_replay=include_replay)
    if not files:
        return Outcome.blocked(
            'MIGRATION_CORPUS_EMPTY',
            'sealed_index.live_draw_files() returned no boards. An empty '
            'corpus is an error, not a result.', cause=Cause.DATA)
    entries = []
    tal = {'MIGRATED': 0, 'NOT_APPLICABLE': 0, 'UNMIGRATABLE': 0, 'ERROR': 0}
    for f in files:
        o = migrate(f.parent, out_root=out_root, write=write)
        rel = str(f.parent.resolve().relative_to(_REPO))
        if o.state is State.PASS:
            tal['MIGRATED'] += 1
            entries.append({
                'source': rel, 'status': 'MIGRATED',
                'migrated_run_id': o.value['run_id'],
                'dest': _rel_or_abs(o.value['dest']),
                'violations_before': o.value['doc']['coherence_before'],
                'violations_after': o.value['doc']['coherence_after']})
        elif o.state is State.NOT_APPLICABLE:
            tal['NOT_APPLICABLE'] += 1
            entries.append({'source': rel, 'status': 'NOT_APPLICABLE',
                            'code': o.code,
                            'family': (o.evidence or {}).get('family'),
                            'detail': o.detail[:300]})
        elif o.code == 'MIGRATION_REFUSED':
            tal['UNMIGRATABLE'] += 1
            entries.append({
                'source': rel, 'status': 'UNMIGRATABLE', 'code': o.code,
                'refusals': (o.evidence or {}).get('refusals'),
                'what_would_be_needed': (
                    'an SC1-style coupling that reserves intercepted throws '
                    'out of the targeted-throw budget before RC1 converts it '
                    'to catches. That is a pre-registered mechanism change in '
                    'shared_pass.targeted_throws, not a patch, and clipping '
                    'the draw here is refused.'),
                'detail': o.detail[:400]})
        else:
            tal['ERROR'] += 1
            entries.append({'source': rel, 'status': 'ERROR', 'code': o.code,
                            'state': o.state.value, 'detail': o.detail[:400]})
    if tal['MIGRATED'] == 0:
        return Outcome.fail(
            'MIGRATION_PRODUCED_NOTHING',
            f'{len(files)} board(s) scanned and none migrated. A migration '
            f'that migrated nothing is not a migration that had nothing to do.',
            **tal)
    return Outcome.ok(
        'MIGRATION_RUN',
        value={'entries': entries, 'tallies': tal, 'n_scanned': len(files)},
        detail=f'{len(files)} board(s) scanned: {tal["MIGRATED"]} migrated, '
               f'{tal["NOT_APPLICABLE"]} already coherent, '
               f'{tal["UNMIGRATABLE"]} unmigratable, {tal["ERROR"]} error',
        **tal)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    write = '--dry-run' not in argv
    o = run(include_replay=True, write=write)
    print(o.state.value, o.code, '--', o.detail)
    if o.state is not State.PASS:
        return 1
    if write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(
            {'spec_version': SPEC_VERSION, 'replacement': REPLACEMENT,
             'superseded': SUPERSEDED,
             'migrated_root': str(MIGRATED_ROOT.relative_to(_REPO)),
             'tallies': o.value['tallies'], 'n_scanned': o.value['n_scanned'],
             'entries': o.value['entries']},
            indent=1, sort_keys=True, default=str) + '\n')
        print('ledger ->', LEDGER.relative_to(_REPO))
    for e in o.value['entries']:
        if e['status'] in ('UNMIGRATABLE', 'ERROR'):
            print(' ', e['status'], e['source'], e.get('code'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
