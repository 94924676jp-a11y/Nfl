"""R7: the appearance frame and depth repair. Guards, not preferences.

Every check here fails if the control it guards is removed. The two that
matter most are the point-in-time refusal (a later chart must never answer for
an earlier game) and the unsupported-cell decline (a degenerate 1.0000 must
never be scored as a probability).
"""
from __future__ import annotations

import datetime as dt
import gzip
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import candidate_mode as CM                      # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7                  # noqa: E402
from nfl.production.nonqb import depth_vintage as DV                 # noqa: E402
from nfl.production.nonqb import layers as LY                        # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


DAILY = ('dt,team,gsis_id,pos_abb,pos_rank\n'
         '2025-09-01T10:00:00Z,SF,00-0000001,WR,1\n'
         '2025-09-01T10:00:00Z,SF,00-0000002,WR,2\n'
         '2025-09-05T10:00:00Z,SF,00-0000001,WR,2\n'
         '2025-09-05T10:00:00Z,SF,00-0000002,WR,1\n'
         '2025-09-08T10:00:00Z,SF,00-0000003,WR,1\n')


# ------------------------------------------------------------- identity
def test_r7_inherits_r6_and_adds_exactly_one_flag():
    r6 = CM.resolve(CM.V1_CANDIDATE_R6).value['flags']
    r7 = CM.resolve(CM.V1_CANDIDATE_R7).value['flags']
    check('R7 keeps every R6 flag',
          all(r7.get(k) == v for k, v in r6.items()), str(r7))
    check('  and adds exactly one',
          set(r7) - set(r6) == {'appearance_r7'}, str(set(r7) - set(r6)))
    for mode in (CM.V1_CANDIDATE, CM.V1_CANDIDATE_R5, CM.V1_CANDIDATE_R6):
        fl = CM.resolve(mode).value['flags']
        check(f'  {mode} does not carry appearance_r7',
              'appearance_r7' not in fl, str(fl))
    comps = [c['component'] for c in
             CM.resolve(CM.V1_CANDIDATE_R7).value['components']]
    check('  R7 is a declared component of its own mode', 'R7' in comps,
          str(comps))
    check('  and R7 declares it introduces no constant',
          CM.R7_REPAIR.get('introduces_no_constant') is True)


def test_an_unknown_candidate_mode_is_still_refused():
    unknown = 'V1_CANDIDATE_' + 'X' * 8
    check('the synthetic mode is genuinely unknown', unknown not in CM.MODES)
    o = CM.resolve(unknown)
    check('  and resolve refuses it rather than defaulting',
          o.state is State.FAIL and o.code == 'MODEL_CONFIGURATION_UNKNOWN',
          o.code)


# --------------------------------------------------------- point in time
def test_a_later_chart_never_answers_for_an_earlier_game():
    d = DV.daily(DAILY)
    check('the fixture parses', d.state is State.PASS, d.code)
    o = DV.daily_point_in_time(d.value, 'SF', '2025-09-06T00:00:00Z')
    check('the newest chart BEFORE the clock is chosen',
          o.state is State.PASS and o.evidence['chosen_dt'] ==
          '2025-09-05T10:00:00Z', o.evidence.get('chosen_dt'))
    check('  and the later snapshot is counted as rejected',
          o.evidence['n_snapshots_rejected_as_later'] == 1,
          o.evidence.get('n_snapshots_rejected_as_later'))
    check('  and the player only the later chart lists is absent',
          '00-0000003' not in o.value, sorted(o.value))
    # THE GUARD: a clock before every snapshot must REFUSE, not fall through
    # to the newest one.
    q = DV.daily_point_in_time(d.value, 'SF', '2020-01-01T00:00:00Z')
    check('a clock before every snapshot refuses by name',
          q.state is State.DEFERRED and q.code == 'DEPTH_PIT_UNAVAILABLE',
          f'{q.state}[{q.code}]')
    check('  and returns no chart at all', q.value is None or not q.value,
          str(q.value)[:80])


def test_a_snapshot_exactly_at_the_clock_is_not_used():
    d = DV.daily(DAILY)
    o = DV.daily_point_in_time(d.value, 'SF', '2025-09-05T10:00:00Z')
    check('the boundary is STRICTLY before, so the 09-05 chart is refused',
          o.state is State.PASS and o.evidence['chosen_dt'] ==
          '2025-09-01T10:00:00Z', o.evidence.get('chosen_dt'))


def test_point_in_time_without_a_clock_is_a_failure_not_a_default():
    d = DV.daily(DAILY)
    o = DV.daily_point_in_time(d.value, 'SF', None)
    check('no clock is a named FAIL, not "use the newest"',
          o.state is State.FAIL and o.code == 'DEPTH_PIT_NO_CLOCK', o.code)


def test_an_unknown_team_refuses_rather_than_returning_an_empty_chart():
    d = DV.daily(DAILY)
    o = DV.daily_point_in_time(d.value, 'ZZZ', '2025-09-06T00:00:00Z')
    check('a team with no chart refuses',
          o.state is State.DEFERRED and o.code == 'DEPTH_PIT_UNAVAILABLE',
          f'{o.state}[{o.code}]')


def test_an_empty_daily_source_is_an_error_not_a_result():
    o = DV.daily('dt,team,gsis_id,pos_abb,pos_rank\n')
    check('an empty chart fails by name',
          o.state is State.FAIL and o.code == 'DEPTH_DAILY_EMPTY', o.code)


def test_a_missing_weekly_leaf_is_named_not_skipped():
    o = DV.weekly('/nonexistent-directory-for-this-test')
    check('a missing weekly leaf blocks by name',
          o.state is State.BLOCKED and o.code == 'DEPTH_WEEKLY_LEAF_MISSING',
          f'{o.state}[{o.code}]')
    check('  and names which seasons were absent',
          list(o.evidence.get('seasons_absent') or []) == list(range(2020, 2025)),
          str(o.evidence.get('seasons_absent')))


def test_captured_refuses_when_no_blob_predates_the_clock():
    o = DV.captured(['SF', 'LA'], '2020-01-01T00:00:00Z')
    check('a clock before every capture refuses',
          o.state is State.DEFERRED and
          o.code == 'DEPTH_CAPTURE_NOT_POINT_IN_TIME', f'{o.state}[{o.code}]')


# --------------------------------------------- depth reaches the model
def test_depth_rank_actually_changes_the_design_row():
    """The frozen defect: f_depth is computed and then never featurised."""
    base = {'s': 2026, 'w': 5, 'pos': 'WR', 'rank': 1, 'n_prior': 10,
            'cm_within': 0, 'cm_carried': 0, 'crossed': False,
            'app_ewma': 0.9, 'prev_appeared': 1, 'inj_available': 0,
            'vendor': DV.DAILY_VENDOR}
    a = R7.featurise(base)
    b = R7.featurise({**base, 'rank': 3})
    c = R7.featurise({**base, 'rank': None})
    check('rank 1 and rank 3 give different design rows', a != b)
    check('rank 1 and unlisted give different design rows', a != c)
    check('  and the row length is stable',
          len(a) == len(b) == len(c) == R7.N_FEATURES, f'{len(a)}')
    # And the frozen featuriser is confirmed NOT to read depth, which is the
    # defect this candidate exists for. If this ever starts failing, the
    # frozen model has changed and R7's premise needs restating.
    import stage_a as A                                      # noqa: E402
    import p3_features as F                                  # noqa: E402
    from nfl.production.nonqb import appearance_model as AM  # noqa: E402
    st = AM.stage_inputs()
    if st.state is State.PASS:
        AM._frozen()
        r = {'position': 'WR', 'f_n_prior': 10, 'f_consec_missed': 0,
             'f_prev_appeared': 1, 'f_depth': 1}
        x1 = F.featurise_p3(r, True, set(F.FEATURE_GROUPS))
        x2 = F.featurise_p3({**r, 'f_depth': 99}, True, set(F.FEATURE_GROUPS))
        check('  the FROZEN featuriser still ignores f_depth (the defect)',
              x1 == x2)


# ------------------------------------------------- season boundary
def test_the_absence_streak_resets_at_the_season_boundary():
    rows = [{'s': 2024, 'w': 16, 't': 'SF', 'pid': 'p', 'pos': 'WR',
             'rank': 1, 'appeared': 1, 'vendor': DV.DAILY_VENDOR},
            {'s': 2024, 'w': 17, 't': 'SF', 'pid': 'p', 'pos': 'WR',
             'rank': 1, 'appeared': 0, 'vendor': DV.DAILY_VENDOR},
            {'s': 2024, 'w': 18, 't': 'SF', 'pid': 'p', 'pos': 'WR',
             'rank': 1, 'appeared': 0, 'vendor': DV.DAILY_VENDOR},
            {'s': 2025, 'w': 1, 't': 'SF', 'pid': 'p', 'pos': 'WR',
             'rank': 1, 'appeared': 1, 'vendor': DV.DAILY_VENDOR}]
    R7._walk(rows, {})
    wk1 = rows[-1]
    check('the within-season streak is 0 at week 1', wk1['cm_within'] == 0,
          str(wk1['cm_within']))
    check('  the carried streak keeps the two missed games',
          wk1['cm_carried'] == 2, str(wk1['cm_carried']))
    check('  and the boundary crossing is recorded', wk1['crossed'] is True)
    check('  while the last in-season row still carries its streak',
          rows[2]['cm_within'] == 1, str(rows[2]['cm_within']))
    # The two are separately encoded, so the model can give them different
    # signs. If they were one feature this check could not exist.
    a = R7.featurise(wk1)
    b = R7.featurise({**wk1, 'cm_carried': 0})
    check('  and the carried streak has its own column', a != b)


# ------------------------------------------- the unsupported cell
def test_the_degenerate_cell_is_declined_not_scored():
    cold_unlisted = {'n_prior': 0, 'rank': None}
    cold_listed = {'n_prior': 0, 'rank': 2}
    known = {'n_prior': 9, 'rank': None}
    check('no history and no depth listing is unsupported',
          R7.is_unsupported(cold_unlisted))
    check('  no history WITH a depth listing is supported',
          not R7.is_unsupported(cold_listed))
    check('  and history without a listing is supported',
          not R7.is_unsupported(known))


def test_the_three_states_are_not_collapsed():
    check('no prior row is NO_HISTORY',
          R7.state_of({'n_prior': 0, 'rank': 1, 'inj_available': 1})
          == R7.NO_HISTORY)
    check('  seen before, no listing and no injury row is UNKNOWN_STATUS',
          R7.state_of({'n_prior': 5, 'rank': None, 'inj_available': 0})
          == R7.UNKNOWN_STATUS)
    check('  seen before and listed is KNOWN_HEALTHY',
          R7.state_of({'n_prior': 5, 'rank': 1, 'inj_available': 0})
          == R7.KNOWN_HEALTHY)
    check('  and the three names are distinct',
          len({R7.KNOWN_HEALTHY, R7.NO_HISTORY, R7.UNKNOWN_STATUS}) == 3)


def test_the_fit_drops_the_unsupported_cell_and_says_how_many():
    f = R7.fit(2026)
    if not check('the R7 fit runs', f.state is State.PASS, f.code):
        return
    n = f.evidence.get('n_dropped_unsupported_cell')
    check('  the fit reports how many rows it dropped',
          isinstance(n, int) and n > 0, str(n))
    check('  and names the cell',
          f.evidence.get('unsupported_cell') == R7.UNSUPPORTED_CELL)
    check('  training stops strictly before the forecast season',
          max(f.evidence['train_seasons']) < 2026,
          str(f.evidence['train_seasons']))


def test_the_frame_is_not_the_censored_panel():
    fr = R7.build_frame()
    if not check('the frame builds', fr.state is State.PASS, fr.code):
        return
    check('  the depth chart adds rows the panel does not hold',
          fr.evidence['n_added_by_depth_chart'] > 1000,
          str(fr.evidence['n_added_by_depth_chart']))
    check('  every team-week got a lawful chart',
          fr.evidence['n_team_weeks_without_a_lawful_chart'] == 0,
          str(fr.evidence['team_weeks_without_a_lawful_chart'])[:200])
    check('  and both vendor eras are present',
          fr.evidence['weekly_vendor_seasons'] and
          fr.evidence['daily_vendor_seasons'],
          f"{fr.evidence['weekly_vendor_seasons']} / "
          f"{fr.evidence['daily_vendor_seasons']}")


def test_the_censoring_this_repair_exists_for_is_still_measurable():
    """The frozen panel inverts at LOOKBACK_CANDIDATE; the frame does not."""
    from nfl.production.nonqb import appearance_model as AM  # noqa: E402
    st = AM.stage_inputs()
    if st.state is not State.PASS:
        print('  ..   panel unavailable; censoring comparison skipped')
        return
    import model as M                                        # noqa: E402
    check('the lookback that causes the censoring is still 4',
          M.LOOKBACK_CANDIDATE == 4, str(M.LOOKBACK_CANDIDATE))
    fr = R7.build_frame()
    if fr.state is not State.PASS:
        return
    rows = sorted(fr.value, key=lambda r: (r['s'], r['w']))
    n = a = 0
    for r in rows:
        if r.get('cm_within', 0) == 4:
            n += 1
            a += r['appeared']
    check('  and at streak 4 the frame holds genuine non-appearances',
          n > 200 and (n - a) > 100, f'n={n} non_appearing={n - a}')


# ------------------------------------------------- the layer seam
def test_an_unknown_appearance_spec_fails_rather_than_falling_back():
    o = LY._run_real(2026, 1, [], [], 20260908, 4, test_only=True,
                     appearance_spec='not-a-mechanism')
    check('an unknown mechanism name is a named FAIL',
          o.state is State.FAIL and o.code == 'APPEARANCE_SPEC_UNKNOWN',
          f'{o.state}[{o.code}]')


def test_the_layer_default_is_still_the_frozen_mechanism():
    import inspect
    sig = inspect.signature(LY.appearance)
    check('layers.appearance defaults to the frozen spec',
          sig.parameters['appearance_spec'].default == 'frozen',
          str(sig.parameters['appearance_spec'].default))
    from nfl.production.nonqb import football_engine as FE   # noqa: E402
    sig2 = inspect.signature(FE.run_game)
    check('  and so does football_engine.run_game',
          sig2.parameters['appearance_spec'].default == 'frozen',
          str(sig2.parameters['appearance_spec'].default))


def test_no_player_or_team_is_hard_coded():
    for mod in ('nfl/production/nonqb/appearance_r7.py',
                'nfl/production/nonqb/depth_vintage.py'):
        src = open(os.path.join(_ROOT, mod)).read()
        for bad in ('Nacua', 'McCaffrey', 'Kittle', 'Adams', 'Purdy',
                    'Stafford', "'SF'", "'LA'"):
            check(f'  {mod.split("/")[-1]}: no hard-coded {bad}',
                  bad not in src, bad)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
