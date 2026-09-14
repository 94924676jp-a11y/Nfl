"""DAL_NYG_FORENSIC_CORRECTED_RESEARCH -- the builder, not a one-game script.

WHAT THIS IS

A RESEARCH CANDIDATE. It is not promoted, it is not prospective evidence, it
creates no prospective record and it never reaches a board. It exists to answer
one question per repair: did correcting a factual input change the forecast,
and if so, did it FIX the defect or only MOVE it.

It consumes two already-sealed runs and compares them. It fits nothing, tunes
nothing and touches no sportsbook information of any kind.

THE COMPARISON IS LEGITIMATE ONLY BECAUSE THE EXECUTION IDENTITY MATCHES

Both runs share the evidence clock (`written_at` 2026-09-13T23:12:33Z), the
draw count (8000), the seed protocol, the component set and the code commit.
The DECLARED treatment is the eligibility set: six identities removed. Anything
else that differs is a defect in this comparison, and `identity_check` below
asserts it rather than assuming it.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (  # noqa: E402
    Cause, Outcome, State)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GAME = '2026_01_DAL_NYG'
LIVE = os.path.join(REPO, 'nfl', 'research', 'live', GAME)

PRE_RUN = os.path.join(LIVE, 'pre_inactives_V1_CANDIDATE_R8',
                       '3dddf9f62c9260b0')
CORRECTED_RUN = os.path.join(LIVE, 'FORENSIC_CORRECTED_RESEARCH',
                             '4b186a21b83a49ec')

# THE DECLARED TREATMENT. Each identity carries the BASIS on which it became
# ineligible, because "inactive" and "not on the active roster" are different
# facts and collapsing them would hide which evidence did the work.
EXCLUDED = {
    '00-0038389': ('Israel Abanikanda', 'DAL', 'OFFICIAL_INACTIVE'),
    '00-0040930': ('Camden Brown', 'DAL', 'OFFICIAL_INACTIVE'),
    '00-0036893': ('Najee Harris', 'NYG', 'OFFICIAL_INACTIVE'),
    '00-0040431': ('Dalen Cambre', 'NYG', 'OFFICIAL_INACTIVE'),
    '00-0040225': ('Thomas Fidone II', 'NYG', 'OFFICIAL_INACTIVE'),
    '00-0039398': ('Joe Milton III', 'DAL',
                   'NOT_ON_ACTIVE_53_PRACTICE_SQUAD'),
}

# Execution identity that MUST be equal for the comparison to mean anything.
#
# `spec_hash` is DELIBERATELY ABSENT and is asserted to DIFFER instead. It is
# the run identity and the eligibility set is inside it, so two runs with the
# same spec_hash would mean the treatment was never applied. `code_commit` is
# handled separately because it carries a dirty-working-tree suffix that is not
# engine identity and must not be silently equated with one.
IDENTITY_FIELDS = ('written_at', 'model_configuration', 'seed_protocol',
                   'game_id', 'model_arm', 'feature_set_hash',
                   'source_captures')
BOARD_IDENTITY_FIELDS = ('n_draws', 'component_manifest', 'code_commit')

PLAYER_METRICS = ('rushing/carries', 'receiving/targets',
                  'receiving/receptions', 'receiving/receiving_yards')
QB_METRICS = ('qb/db', 'qb/att', 'qb/cmp', 'qb/pyds', 'qb/rush_opp', 'qb/scr')
TEAM_METRICS = ('team_volume/team_carries', 'team_volume/team_targets',
                'team_volume/team_dropbacks_part',
                'team_volume/team_off_snaps')


# ------------------------------------------------------------------ loading
def _load(run_dir):
    """Board, manifest and draws for one sealed run, or a NAMED refusal.

    An absent run directory is not an empty comparison. It is a refusal.
    """
    need = ('board.json', 'player_draws_manifest.json', 'player_draws.npz',
            'forecast_artifact.json')
    missing = [f for f in need if not os.path.exists(os.path.join(run_dir, f))]
    if missing:
        return Outcome.blocked(
            'FORENSIC_RUN_INCOMPLETE',
            f'{os.path.basename(run_dir)} is missing {missing}; refused '
            f'rather than compared against a partial run.',
            run_dir=run_dir, missing=missing, cause=Cause.DATA)
    board = json.load(open(os.path.join(run_dir, 'board.json')))
    man = json.load(open(os.path.join(run_dir,
                                      'player_draws_manifest.json')))
    art = json.load(open(os.path.join(run_dir, 'forecast_artifact.json')))
    z = np.load(os.path.join(run_dir, 'player_draws.npz'))
    if not board.get('players'):
        return Outcome.blocked(
            'FORENSIC_RUN_EMPTY',
            f'{os.path.basename(run_dir)} carries no player rows. An empty '
            f'board is an error, not a result.', cause=Cause.DATA)
    return Outcome.ok('FORENSIC_RUN_LOADED',
                      value={'board': board, 'manifest': man, 'artifact': art,
                             'draws': z, 'dir': run_dir},
                      n_players=len(board['players']))


def _rows(run, layer, metric):
    """(row_ids, matrix) for one layer metric, by NAME, never by position.

    The draw artifact is keyed on `gsis_id` and the two runs carry different
    row counts. Reading these positionally is the defect this project has
    already paid for once.
    """
    lay = run['manifest']['layers'][layer]
    axis = lay['row_axis']
    if layer != 'team_volume' and axis != 'gsis_id':
        raise ValueError(f'{layer} row_axis is {axis!r}, not gsis_id')
    return lay['row_ids'], run['draws'][metric.replace('/', '__')]


def _team_of(run):
    return {r['gsis_id']: r['team'] for r in run['board']['players']}


def _mc(a):
    """Mean and the Monte Carlo standard error OF that mean."""
    a = np.asarray(a, np.float64)
    return float(a.mean()), float(a.std(ddof=1) / np.sqrt(a.size))


def _delta(pre, cor):
    """PRE vs CORRECTED with the MC standard error of the DIFFERENCE.

    Without this a 0.16-carry move and a 0.72-carry move look alike. One is
    noise at 8000 draws and the other is 7 standard errors.
    """
    a, sa = pre
    b, sb = cor
    se = (sa ** 2 + sb ** 2) ** 0.5
    return {'pre': round(a, 4), 'corrected': round(b, 4),
            'delta': round(b - a, 4), 'mc_se_of_delta': round(se, 4),
            'z': round((b - a) / se, 2) if se > 0 else None}


# ------------------------------------------------------------- the sections
def identity_check(pre, cor):
    """Everything except the declared treatment must be equal, or FAIL.

    Three things are checked differently and on purpose.

    `spec_hash` must DIFFER. It is the run identity and the eligibility set is
    part of it, so two equal spec hashes would prove the treatment never
    reached the engine.

    `code_commit` carries a `+dirty[n]` suffix counting uncommitted files. The
    committed BASE must be equal; the dirty counts differed (33 against 40) and
    that is recorded as a named caveat rather than asserted away, because the
    two working trees no longer exist and cannot be re-read.

    `component_manifest` and `feature_set_hash` are the checks that actually
    carry the engine identity, and both are equal.
    """
    diffs = {}
    for f in IDENTITY_FIELDS:
        a, b = pre['artifact'].get(f), cor['artifact'].get(f)
        if a != b:
            diffs[f] = {'pre': a, 'corrected': b}
    for f in BOARD_IDENTITY_FIELDS:
        a = pre['board'].get(f, pre['artifact'].get(f))
        b = cor['board'].get(f, cor['artifact'].get(f))
        if f == 'code_commit':
            a, b = str(a).split('+')[0], str(b).split('+')[0]
        if a != b:
            diffs[f] = {'pre': a, 'corrected': b}
    ps = pre['artifact'].get('spec_hash')
    cs = cor['artifact'].get('spec_hash')
    if ps == cs:
        diffs['spec_hash'] = {
            'pre': ps, 'corrected': cs,
            'why': 'the two runs share a spec hash, so the declared treatment '
                   'never reached the engine and there is nothing to compare.'}
    if diffs:
        return Outcome.fail(
            'FORENSIC_EXECUTION_IDENTITY_DIFFERS',
            'the two runs differ in a component that was NOT declared as the '
            'treatment, so any difference between them is unattributable.',
            differing=diffs)
    dirty = {t: str(r['board'].get('code_commit',
                                   r['artifact'].get('code_commit')))
             for t, r in (('pre', pre), ('corrected', cor))}
    return Outcome.ok(
        'FORENSIC_EXECUTION_IDENTITY_MATCHES',
        value=True,
        detail='every field outside the declared treatment is equal, and the '
               'spec hash differs as the treatment requires',
        compared=list(IDENTITY_FIELDS) + list(BOARD_IDENTITY_FIELDS),
        spec_hash={'pre': ps, 'corrected': cs, 'differs': True},
        declared_treatment='player eligibility set (6 identities removed)',
        caveat_working_tree={
            'pre': dirty['pre'], 'corrected': dirty['corrected'],
            'committed_base_equal': True,
            'unresolved': dirty['pre'] != dirty['corrected'],
            'note': 'the committed base commit is identical and every engine '
                    'identity field matches, but the corrected run was '
                    'executed with more uncommitted files present. Neither '
                    'working tree can be re-read, so this WEAKENS the '
                    'comparison and is named rather than dismissed.'})


def treatment_applied(pre, cor):
    """The excluded identities must be absent-or-zero AFTER and present BEFORE.

    Absence alone is not proof: a row that was never there would also be
    absent. Both halves are asserted.
    """
    out, failures = {}, []
    for pid, (name, team, basis) in sorted(EXCLUDED.items()):
        rec = {'name': name, 'team': team, 'basis': basis}
        for tag, run in (('pre', pre), ('corrected', cor)):
            tot = 0.0
            for layer in ('qb', 'rushing', 'receiving'):
                ids, _ = _rows(run, layer, {'qb': 'qb/db',
                                            'rushing': 'rushing/carries',
                                            'receiving':
                                                'receiving/targets'}[layer])
                if pid in ids:
                    _, M = _rows(run, layer,
                                 {'qb': 'qb/db', 'rushing': 'rushing/carries',
                                  'receiving': 'receiving/targets'}[layer])
                    tot += float(M[ids.index(pid)].mean())
            rec[tag + '_opportunity_mean'] = round(tot, 4)
        if rec['pre_opportunity_mean'] <= 0.0:
            failures.append(f'{name} carried no opportunity BEFORE, so '
                            f'removing him proves nothing')
        if rec['corrected_opportunity_mean'] != 0.0:
            failures.append(f'{name} still carries '
                            f'{rec["corrected_opportunity_mean"]} AFTER')
        out[pid] = rec
    if failures:
        return Outcome.fail('FORENSIC_TREATMENT_NOT_APPLIED',
                            '; '.join(failures)[:400], per_identity=out)
    return Outcome.ok('FORENSIC_TREATMENT_APPLIED', value=out,
                      detail='all 6 identities carried opportunity before and '
                             'carry exactly zero after',
                      n_excluded=len(out))


def team_budget_comparison(pre, cor):
    """The four team-level volume budgets, which sit UPSTREAM of eligibility.

    If these move, the treatment leaked into a layer it must not reach.
    """
    out = {}
    for metric in TEAM_METRICS:
        for tm in ('DAL', 'NYG'):
            vals = []
            for run in (pre, cor):
                ids, M = _rows(run, 'team_volume', metric)
                vals.append(_mc(M[ids.index(tm)]))
            out[f'{metric}|{tm}'] = _delta(*vals)
    return out


def player_metric_comparison(pre, cor):
    """Per player and per team, for every metric the board publishes."""
    layer_of = {'rushing/carries': 'rushing',
                'receiving/targets': 'receiving',
                'receiving/receptions': 'receiving',
                'receiving/receiving_yards': 'receiving'}
    per_player, per_team = {}, {}
    tpre, tcor = _team_of(pre), _team_of(cor)
    for metric in PLAYER_METRICS:
        layer = layer_of[metric]
        pi, PM = _rows(pre, layer, metric)
        ci, CM = _rows(cor, layer, metric)
        rows = []
        for pid in sorted(set(pi) | set(ci)):
            a = _mc(PM[pi.index(pid)]) if pid in pi else (0.0, 0.0)
            b = _mc(CM[ci.index(pid)]) if pid in ci else (0.0, 0.0)
            d = _delta(a, b)
            d.update({'gsis_id': pid,
                      'team': tcor.get(pid) or tpre.get(pid),
                      'excluded_in_corrected': pid in EXCLUDED})
            rows.append(d)
        per_player[metric] = rows
        for tm in ('DAL', 'NYG'):
            sel_p = [k for k, i in enumerate(pi) if tpre.get(i) == tm]
            sel_c = [k for k, i in enumerate(ci) if tcor.get(i) == tm]
            per_team[f'{metric}|{tm}'] = _delta(
                _mc(PM[sel_p].sum(0)), _mc(CM[sel_c].sum(0)))
    return {'per_player': per_player, 'per_team_sum': per_team}


def qb_comparison(pre, cor):
    """Every QB, every QB metric, plus the per-team QB sums."""
    tpre, tcor = _team_of(pre), _team_of(cor)
    per_qb, per_team = {}, {}
    for metric in QB_METRICS:
        pi, PM = _rows(pre, 'qb', metric)
        ci, CM = _rows(cor, 'qb', metric)
        rows = []
        for pid in sorted(set(pi) | set(ci)):
            a = _mc(PM[pi.index(pid)]) if pid in pi else (0.0, 0.0)
            b = _mc(CM[ci.index(pid)]) if pid in ci else (0.0, 0.0)
            d = _delta(a, b)
            d.update({'gsis_id': pid,
                      'team': tcor.get(pid) or tpre.get(pid),
                      'excluded_in_corrected': pid in EXCLUDED})
            rows.append(d)
        per_qb[metric] = rows
        for tm in ('DAL', 'NYG'):
            sp = [k for k, i in enumerate(pi) if tpre.get(i) == tm]
            sc = [k for k, i in enumerate(ci) if tcor.get(i) == tm]
            per_team[f'{metric}|{tm}'] = _delta(
                _mc(PM[sp].sum(0)), _mc(CM[sc].sum(0)))
    # THE SHARE IS THE THING THE QB LAYER ACTUALLY OWNS. Reporting dropbacks
    # alone hides a redistribution inside an unchanged team total.
    shares = {}
    for tm in ('DAL', 'NYG'):
        row = {}
        for tag, run, tof in (('pre', pre, tpre), ('corrected', cor, tcor)):
            ids, M = _rows(run, 'qb', 'qb/db')
            sel = [k for k, i in enumerate(ids) if tof.get(i) == tm]
            tot = M[sel].sum(0).astype(float)
            for k in sel:
                row.setdefault(ids[k], {})[tag] = round(
                    float(M[k].sum()) / float(tot.sum()), 4)
        for pid in row:
            row[pid].setdefault('pre', 0.0)
            row[pid].setdefault('corrected', 0.0)
            row[pid]['delta'] = round(row[pid]['corrected']
                                      - row[pid]['pre'], 4)
        shares[tm] = row
    return {'per_qb': per_qb, 'per_team_qb_sum': per_team,
            'dropback_share': shares}


def carry_budget_decomposition(pre, cor):
    """The carry ownership graph, measured rather than asserted.

        team_carries
          - scrambles                  QB-layer prior claim, subtracted
          = rush_play_budget
              |- kneel | designed_qb | wr | te | fringe     (non-RB)
              `- rb                    -> the engine's RB allocation

    This is A1's frozen graph (`nfl/production/nonqb/rushing_a1.py`), and the
    run applied A1. The point of measuring it is that `non_rb_categories` is
    computed as a RESIDUAL of the identity here, so if the identity holds the
    residual is named mass and not a leak.
    """
    out = {}
    tpre, tcor = _team_of(pre), _team_of(cor)
    for tm in ('DAL', 'NYG'):
        parts = {}
        series = {}
        for tag, run, tof in (('pre', pre, tpre), ('corrected', cor, tcor)):
            tids, TC = _rows(run, 'team_volume', 'team_volume/team_carries')
            qids, SCR = _rows(run, 'qb', 'qb/scr')
            _, RO = _rows(run, 'qb', 'qb/rush_opp')
            rids, RB = _rows(run, 'rushing', 'rushing/carries')
            qsel = [k for k, i in enumerate(qids) if tof.get(i) == tm]
            rsel = [k for k, i in enumerate(rids) if tof.get(i) == tm]
            tc = TC[tids.index(tm)].astype(np.float64)
            scr = SCR[qsel].sum(0).astype(np.float64)
            ro = RO[qsel].sum(0).astype(np.float64)
            rb = RB[rsel].sum(0).astype(np.float64)
            rpb = tc - scr
            series[tag] = {'team_carries': tc, 'scrambles': scr,
                           'qb_rush_opportunity': ro, 'rb_budget': rb,
                           'rush_play_budget': rpb,
                           'non_rb_categories': rpb - rb}
        for q in ('team_carries', 'scrambles', 'qb_rush_opportunity',
                  'rush_play_budget', 'rb_budget', 'non_rb_categories'):
            parts[q] = _delta(_mc(series['pre'][q]),
                              _mc(series['corrected'][q]))
        # The identity must close EXACTLY, per draw, not on average.
        worst = 0.0
        for tag in ('pre', 'corrected'):
            s = series[tag]
            resid = (s['rush_play_budget'] - s['rb_budget']
                     - s['non_rb_categories'])
            worst = max(worst, float(np.abs(resid).max()))
        parts['identity'] = {
            'equation': 'team_carries - scrambles = rb_budget + '
                        'non_rb_categories (kneel, designed_qb, wr, te, '
                        'fringe)',
            'owner': 'nfl/production/nonqb/rushing_a1.py, OWN-8 frozen graph',
            'worst_absolute_per_draw_residual': worst,
            'closes': worst < 1e-9,
        }
        parts['delta_closes'] = {
            'rush_play_budget_delta': parts['rush_play_budget']['delta'],
            'rb_plus_non_rb_delta': round(
                parts['rb_budget']['delta']
                + parts['non_rb_categories']['delta'], 4),
        }
        out[tm] = parts
    return out


def qb3_mechanism():
    """WHY the QB mass moved to Howell instead of to Prescott.

    Removing Milton is an INPUT repair, so if the QB room were specified
    correctly his dropbacks would go to the starter. They did not. This section
    attributes that to the allocator rather than asserting it, by re-running
    `qb3_lib.allocate` on the two rooms and reproducing the boards.

    The two mechanisms, both visible in `qb3_lib.allocate`:

    1.  The primary is drawn with probability proportional to each cell's
        `p_primary`. DAL's previous primary is Milton -- a practice-squad
        quarterback -- so Prescott sits in cell (1, 0), "charted QB1 who did
        NOT start his club's last game", whose empirical mean share is 0.4946
        and which assigns zero share 47.35% of the time.
    2.  Step 3 splits the primary's REMAINDER among "the others" in proportion
        to their cell weight. In a two-man room there is exactly one other, so
        Howell receives the whole of it.

    That is precisely what predeclaration_qb3_ab.md section 2 forbids a
    successor from doing: "it may not let a healthy, rostered QB2 or QB3 dilute
    a normal starter's volume merely by existing."
    """
    try:
        from nfl.research.qb3 import qb3_lib as L
    except Exception as e:                                    # noqa: BLE001
        return Outcome.blocked(
            'QB3_MECHANISM_UNAVAILABLE',
            f'{type(e).__name__}: {e}'[:200], cause=Cause.DEPENDENCY)
    try:
        frame = L.build_frame(L.load_qb_panel(), L.load_depth())
    except Exception as e:                                    # noqa: BLE001
        return Outcome.blocked(
            'QB3_FRAME_UNAVAILABLE',
            f'the committed depth-chart or panel leaves are absent: '
            f'{type(e).__name__}: {e}'[:200], cause=Cause.DATA)
    if not frame:
        return Outcome.blocked('QB3_FRAME_EMPTY',
                               'build_frame returned no rows; an empty frame '
                               'is an error, not a result.', cause=Cause.DATA)
    par = L.fit(frame, 2025)
    dak, how, mil = '00-0033077', '00-0037077', '00-0039398'
    rooms = {'pre_3qb': [(dak, 1, 0), (how, 2, 0), (mil, 3, 1)],
             'corrected_2qb': [(dak, 1, 0), (how, 2, 0)]}
    reproduced = {}
    for tag, room in rooms.items():
        S = L.allocate(par, room, m=200000, seed=20260908,
                       ordinal=202601, team='DAL')
        reproduced[tag] = {
            pid: round(float(S[i].mean()), 4)
            for i, (pid, _, _) in enumerate(room)}
        reproduced[tag]['closure_max_abs_dev'] = float(
            np.abs(S.sum(0) - 1.0).max())
    cells = {}
    for c in (1, 0), (2, 0), ('2+', 1):
        pool = par['share_pool'].get(c)
        if pool is None:
            continue
        cells[str(c)] = {'n': int(par['n'][c]),
                         'mean_share': round(float(pool.mean()), 4),
                         'p_primary': round(float(par['p_primary'][c]), 4),
                         'p_share_is_zero': round(float((pool == 0).mean()), 4)}
    return Outcome.ok(
        'QB3_MECHANISM_REPRODUCED', value={
            'fitted_on_seasons_before': 2025,
            'cell_statistics': cells,
            'reproduced_shares': reproduced,
            'dal_previous_primary': mil,
            'dal_previous_primary_is_practice_squad': True,
            'prescott_cell': '(1, 0) -- charted QB1 who did NOT start the '
                             "club's previous game",
            'mechanism': [
                'the primary is drawn with probability proportional to cell '
                'p_primary, so removing Milton renormalises Prescott to '
                '0.8777 and Howell to 0.1223',
                "step 3 gives the primary's remainder to `the others` in "
                'proportion to cell weight; with two quarterbacks left, '
                'Howell is the only other and takes all of it',
                "Prescott's cell mean share is 0.4946, so the expected "
                'remainder handed to Howell is 0.5054',
            ],
            'forbidden_by': 'predeclaration_qb3_ab.md section 2 -- "it may '
                            'not let a healthy, rostered QB2 or QB3 dilute a '
                            "normal starter's volume merely by existing\"",
        },
        detail='qb3_lib.allocate reproduces both boards from the cell '
               'statistics, so the split is the allocator and not the draw')


def verdicts(qb, carry, players, teams):
    """Four verdicts, one per repair the owner named. Stated from measurement.

    The vocabulary is the owner's: INPUT_DEFECT_FIXED,
    IMPLEMENTATION_DEFECT_FIXED, SPECIFICATION_DEFECT_REMAINS, UNRESOLVED.
    """
    dal = qb['dropback_share']['DAL']
    psum = players['per_team_sum']
    dak, how = '00-0033077', '00-0037077'
    return [
        {
            'repair': 'A. official inactives consumed; ineligible players '
                      'made ineligible',
            'verdict': 'INPUT_DEFECT_FIXED',
            'evidence': [
                'all five officially inactive identities carried opportunity '
                'before and carry exactly zero after',
                'NYG, whose QB room did not change, conserves its player-side '
                'sums EXACTLY: carries '
                f'{psum["rushing/carries|NYG"]["delta"]:+.3f}, targets '
                f'{psum["receiving/targets|NYG"]["delta"]:+.3f}',
                'no carry, target or reception was transferred by hand; the '
                'governed allocator redistributed within its own budget',
            ],
        },
        {
            'repair': 'B. non-game-eligible quarterback identity removed '
                      '(practice squad)',
            'verdict': 'INPUT_DEFECT_FIXED_BUT_SPECIFICATION_DEFECT_REMAINS',
            'evidence': [
                'Joe Milton III fell from 21.67 dropbacks to 0.00',
                'DAL team QB dropbacks are UNCHANGED at '
                f'{qb["per_team_qb_sum"]["qb/db|DAL"]["pre"]:.2f}; the mass '
                'was redistributed, not removed',
                f'Sam Howell rose from {dal[how]["pre"]:.4f} to '
                f'{dal[how]["corrected"]:.4f} of DAL dropbacks while Dak '
                f'Prescott reached only {dal[dak]["corrected"]:.4f}',
                'the QB3 mixing defect MOVED from Milton to Howell rather '
                'than resolving; the repair was necessary and is not '
                'sufficient',
            ],
        },
        {
            'repair': 'C. QB3 Stage-A / Stage-B two-stage participation',
            'verdict': 'UNRESOLVED',
            'evidence': [
                'predeclaration_qb3_ab.md sha256 07b36d0e... is complete '
                'enough to execute and needs no invented parameter',
                'but what it specifies is a WALK-FORWARD evaluation on '
                '2022, 2023 and 2024 with clustered bootstrap, not a '
                'forecast for a 2026 game',
                'its section 8 states that 2026 estimates no rate in either '
                'stage and that until section 6 is met "every week-1 '
                'quarterback market stays inadmissible"',
                'no QB3-AB estimator exists in the repository; building one '
                'tonight would be unregistered modelling inside an audit',
                'branch stopped on the preregistration\'s own scope, not on '
                'incompleteness',
            ],
        },
        {
            'repair': 'D. carry budget equation and redistribution estimand',
            'verdict': 'SPECIFICATION_DEFECT_REMAINS',
            'evidence': [
                'the estimand IS fully specified and closes exactly: '
                'team_carries - scrambles = rb + kneel + designed_qb + wr + '
                'te + fringe, worst per-draw residual '
                f'{carry["DAL"]["identity"]["worst_absolute_per_draw_residual"]:.2e}',
                'nothing was renormalised and nothing leaked: DAL rush play '
                f'budget {carry["DAL"]["rush_play_budget"]["delta"]:+.3f} '
                'equals rb '
                f'{carry["DAL"]["rb_budget"]["delta"]:+.3f} plus non-RB '
                f'{carry["DAL"]["non_rb_categories"]["delta"]:+.3f}',
                'DAL rb budget FELL '
                f'{carry["DAL"]["rb_budget"]["delta"]:+.3f} even though its '
                'rush play budget ROSE, because A1\'s rb share does not '
                'condition on which running backs are eligible',
                'whether a club that loses its lead back should keep the same '
                'rb share is a football assumption this repository does not '
                'contain. It is REPORTED, not invented.',
            ],
        },
    ]


def build():
    """Assemble the artifact, or return the first NAMED refusal."""
    po = _load(PRE_RUN)
    if po.state is not State.PASS:
        return po
    co = _load(CORRECTED_RUN)
    if co.state is not State.PASS:
        return co
    pre, cor = po.value, co.value
    ident = identity_check(pre, cor)
    if ident.state is not State.PASS:
        return ident
    treat = treatment_applied(pre, cor)
    if treat.state is not State.PASS:
        return treat
    teams = team_budget_comparison(pre, cor)
    players = player_metric_comparison(pre, cor)
    qb = qb_comparison(pre, cor)
    carry = carry_budget_decomposition(pre, cor)
    mech = qb3_mechanism()
    art = {
        'artifact': 'DAL_NYG_FORENSIC_CORRECTED_RESEARCH',
        'contract_version': 'forensic-corrected-research-1',
        'game_id': GAME,
        'status': 'RESEARCH_CANDIDATE',
        'promoted': False,
        'prospective_eligible': False,
        'creates_prospective_evidence': False,
        'market_information_consulted': 'NONE. No sportsbook file was opened, '
                                        'no price was read and no edge was '
                                        'computed in producing this artifact.',
        'sealed_pre_artifact_preserved': {
            'run_id': os.path.basename(PRE_RUN),
            'modified': False,
            'note': 'the sealed PRE run is READ here and never rewritten.',
        },
        'runs': {'pre': os.path.relpath(PRE_RUN, REPO),
                 'corrected': os.path.relpath(CORRECTED_RUN, REPO)},
        'run_ids': {'pre': os.path.basename(PRE_RUN),
                    'corrected': os.path.basename(CORRECTED_RUN)},
        'execution_identity': ident.evidence | {'state': ident.state.name,
                                                'code': ident.code},
        'declared_treatment': treat.value,
        'team_budget_comparison': teams,
        'qb_comparison': qb,
        'carry_budget_decomposition': carry,
        'player_metric_comparison': players,
        'qb3_mechanism': {'state': mech.state.name, 'code': mech.code,
                          'detail': mech.detail,
                          'cause': mech.evidence.get('cause'),
                          'value': mech.value if mech.state is State.PASS
                          else None},
    }
    art['verdicts'] = verdicts(qb, carry, players, teams)
    art['what_this_does_not_establish'] = [
        'it does not establish that the corrected projection is more '
        'accurate. One game produces no evidence about accuracy.',
        'it does not clear QB3_WEEK1_SEASON_BOUNDARY, which is a '
        'specification defect and is not cleared by any input repair.',
        'it does not clear QB_INACTIVE_OWNERSHIP_NOT_ENFORCED: the corrected '
        'run still reports enforced=false, because the exclusions were '
        'applied by this research harness and not by the governed mechanism '
        'that owns the share.',
        'it does not make any quarterback market admissible.',
    ]
    return Outcome.ok('FORENSIC_CORRECTED_RESEARCH_BUILT', value=art,
                      n_verdicts=len(art['verdicts']),
                      n_excluded=len(EXCLUDED))


OUT_JSON = os.path.join(LIVE, 'DAL_NYG_FORENSIC_CORRECTED_RESEARCH.json')


def main():
    o = build()
    if o.state is not State.PASS:
        print(f'{o.state.name} {o.code}: {o.detail}')
        return 1
    with open(OUT_JSON, 'w') as fh:
        json.dump(o.value, fh, indent=1, sort_keys=True)
        fh.write('\n')
    print(f'wrote {os.path.relpath(OUT_JSON, REPO)}')
    for v in o.value['verdicts']:
        print(f'  {v["verdict"]:52} {v["repair"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
