"""Candidate B: the appearance V1-presence leak, and the switch that records it.

WHAT THESE TESTS ARE FOR

The incumbent `appearance_r8` keys its V1 feature block on the frozen P3 panel,
which holds a row for a player-team-week if and only if he took a snap. On the
union frame the block is present on 53,626 rows whose appearance rate is 0.7119
and absent on 6,158 rows whose appearance rate is 0.0000 exactly. Feature
presence is very nearly the label in training, and at serve it is a constant.
Candidate B rebuilds the block over the union candidate universe so presence is
a constant everywhere.

Three of these tests are GUARDS rather than demonstrations, and they are the
ones to keep if anything is ever cut:

  * `test_the_incumbent_defect_is_still_there` -- if this stops failing to find
    the defect, either it was fixed elsewhere (and this whole candidate needs
    re-reading) or the frame moved. Either way the comparison below is no
    longer measuring what it says.
  * `test_the_switch_never_falls_back` -- a fallback from a candidate arm to
    the incumbent would run the promoted model behind a requested candidate
    name, which fails in the dangerous direction.
  * `test_layers_py_is_untouched` -- Q9's frozen candidate identity hashes
    `layers.py`. Candidate B must be reachable without editing it.

Run standalone:  python3.12 nfl/tests/test_appearance_candidate_b.py
"""
from __future__ import annotations

import hashlib
import inspect
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, State          # noqa: E402
from nfl.production.nonqb import appearance_arm as AA               # noqa: E402
from nfl.production.nonqb import appearance_b as B                  # noqa: E402
from nfl.production.nonqb import appearance_model as AM             # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7                # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8                # noqa: E402

PASSED = FAILED = BLOCKED = 0

# Q9's frozen candidate identity, from nfl/production/nonqb/layers.py.
Q9_LAYERS_SHA16 = '481f005f682cd721'

# Names no appearance feature may carry. Same list nfl/research/q6/frame.py
# uses, plus the postgame column that was briefly a feature and scored an
# in-sample Brier of 0.04101 before anyone noticed.
FORBIDDEN = ('weekly_rosters.status', 'roster_status', 'status_ina',
             'inactive_list', 'spread', 'vegas', 'total_line', 'odds',
             'final_', 'realized_', 'postgame', 'price', 'book', 'snap_share')

_FRAME = {}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    """Counted apart and never as a pass."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


def _frame():
    """B's union frame and R8's incumbent frame, built once for this module."""
    if _FRAME:
        return _FRAME
    b = B.union_frame()
    r = R8.enriched_frame()
    _FRAME.update({'b': b, 'r8': r})
    return _FRAME


# =================================================== A. the defect, restated
def test_the_incumbent_defect_is_still_there():
    """THE GUARD. The candidate is a repair for a specific, measured defect.

    If this cell has disappeared the defect was fixed somewhere else, and every
    comparison in this module is then measuring something other than what it
    claims. Finding it is a PASS here; that is deliberate and is not an
    endorsement of it.
    """
    F = _frame()
    if F['r8'].state is not State.PASS:
        blocked('the incumbent frame', f'{F["r8"].code}: {F["r8"].detail[:120]}')
        return
    rows = F['r8'].value
    absent = [r for r in rows if r.get('v1') is None]
    present = [r for r in rows if r.get('v1') is not None]
    check('the incumbent frame still has a blockless cell',
          len(absent) > 0, f'{len(absent)} rows')
    if absent:
        rate = sum(r['appeared'] for r in absent) / len(absent)
        check('  and its appearance rate is exactly zero',
              rate == 0.0, f'rate={rate}')
        check('  while the block-bearing rows appear at about 0.71',
              0.69 < sum(r['appeared'] for r in present) / len(present) < 0.73)
    check('  so presence is close to the label, which is the defect',
          len(absent) > 1000, f'{len(absent)}')


def test_the_incumbent_fills_the_block_for_everyone_at_serve():
    """The other half of the defect: at serve the same column is a constant."""
    src = inspect.getsource(R8.predict)
    check('R8.predict fills the V1 block from the prospective walk',
          'prospective_feature_rows' in src)
    check('  for every player, not only the ones with a panel row',
          'for q in players' in src and "r['v1'] = (" in src)
    fsrc = inspect.getsource(R8.featurise)
    check('  and R8 still carries an explicit presence column',
          "f.append(1.0 if r.get('v1') is None else 0.0)" in fsrc)


# ============================================ B. the featuriser, structurally
def test_b_removes_exactly_one_column_and_it_is_the_presence_one():
    """Not asserted -- proved against R8's own output.

    A row whose `v1` is None and a row whose `v1` is an EMPTY dict take
    identical paths through every other line of R8.featurise, because
    `blk = r.get('v1') or {}` maps both to {}. So the two outputs may differ in
    exactly one position and must differ there.
    """
    a = R8.featurise({'w': 5, 'pos': 'WR', 'rank': 2, 'n_cur': 3,
                      'v1': None}, 1.2)
    b = R8.featurise({'w': 5, 'pos': 'WR', 'rank': 2, 'n_cur': 3,
                      'v1': {}}, 1.2)
    moved = [i for i in range(len(a)) if a[i] != b[i]]
    check('exactly one R8 column encodes V1-block presence',
          moved == [len(a) - 1], str(moved))
    check('  it is an indicator, 1 when absent and 0 when present',
          (a[-1], b[-1]) == (1.0, 0.0), f'{a[-1]}, {b[-1]}')
    check('  and Candidate B is R8 minus that one column',
          B.N_FEATURES == R8.N_FEATURES - 1,
          f'{B.N_FEATURES} vs {R8.N_FEATURES}')
    r = {'w': 5, 'pos': 'WR', 'rank': 2, 'n_cur': 3,
         'v1': {k: 0.25 for k in B.V1_KEYS}}
    check('  and is otherwise R8 verbatim, not a second copy of it',
          B.featurise(r, 1.2) == R8.featurise(r, 1.2)[:B.N_FEATURES])
    check('  because it CALLS R8.featurise rather than restating it',
          'R8.featurise(r, k)' in inspect.getsource(B.featurise))


def test_an_absent_block_is_a_named_error_not_an_imputation():
    """Imputing a missing block is Candidate A, which is falsified."""
    try:
        B.featurise({'w': 5, 'pos': 'WR', 'rank': 2, 'n_cur': 3, 'v1': None},
                    1.2)
        check('a blockless row raises rather than being imputed', False,
              'no exception')
    except B.CandidateBError as e:
        check('a blockless row raises rather than being imputed',
              'B_BLOCK_ABSENT' in str(e), str(e)[:120])


def test_no_forbidden_input_reaches_the_feature_set():
    names = [f'v1_{k}' for k in B.V1_KEYS] + ['app_ewma', 'cm_carried',
                                              'n_prior', 'rank', 'inj_status']
    bad = [n for n in names
           if any(f in n.lower() for f in FORBIDDEN)]
    check('no feature name matches a forbidden input', not bad, str(bad))
    src = (_REPO / 'nfl/production/nonqb/appearance_b.py').read_text()
    for token in ('odds', 'vegas', 'hardrock', 'hard_rock', 'spread',
                  'moneyline', 'total_line'):
        check(f'  appearance_b.py never mentions {token}',
              token not in src.lower(), token)


def test_no_player_or_team_is_hard_coded():
    src = (_REPO / 'nfl/production/nonqb/appearance_b.py').read_text()
    for bad in ('Nacua', 'McCaffrey', 'Kittle', 'Mahomes', 'Bowers',
                "'SF'", "'LA'", "'KC'", "'DEN'"):
        check(f'  no hard-coded {bad}', bad not in src, bad)


# ================================================== C. the union basis itself
def test_presence_is_a_constant_on_the_union_basis():
    F = _frame()
    if F['b'].state is not State.PASS:
        blocked('the union frame', f'{F["b"].code}: {F["b"].detail[:120]}')
        return
    rows = F['b'].value
    nb = sum(1 for r in rows if r.get('v1') is None)
    check('every union frame row carries a V1 block', nb == 0, f'{nb} without')
    check('  so the presence rate is exactly one',
          F['b'].evidence.get('v1_presence_rate') == 1.0,
          str(F['b'].evidence.get('v1_presence_rate')))
    check('  and P(appeared | block absent) is undefined for want of a row',
          not [r for r in rows if r.get('v1') is None])
    check('  the frame is the same size as the incumbent\'s',
          len(rows) == len(F['r8'].value or []),
          f'{len(rows)} vs {len(F["r8"].value or [])}')


def test_the_incumbent_frame_is_not_mutated():
    """THE ALIASING GUARD.

    `R8.enriched_frame` serves rows from a module-level cache. Replacing `v1`
    on those objects in place would silently change what the INCUMBENT
    predicts -- 'do not silently replace the incumbent', arrived at by
    aliasing rather than by intent.
    """
    F = _frame()
    if F['b'].state is not State.PASS or F['r8'].state is not State.PASS:
        blocked('the two frames', 'one of them did not build')
        return
    inc = F['r8'].value
    n_absent = sum(1 for r in inc if r.get('v1') is None)
    check('the incumbent frame still has its blockless rows after B ran',
          n_absent > 0, f'{n_absent}')
    b_ids = {id(r) for r in F['b'].value}
    shared = sum(1 for r in inc if id(r) in b_ids)
    check('  and B\'s rows are copies, sharing no object with it',
          shared == 0, f'{shared} shared objects')
    check('  which the code says in as many words',
          'q = dict(r)' in inspect.getsource(B.union_frame))


def test_the_synthetic_rows_are_the_shape_production_builds():
    cols = ['season', 'week', 'team', 'gsis_id', 'targets', 'carries']
    r = B.synthetic_row(2024, 3, 'KC', '00-0000000', 'WR', cols, 1)
    check('a synthetic row zeroes opportunity', r['targets'] == 0
          and r['carries'] == 0)
    check('  carries did_not_appear as a fact, not a guess',
          r['did_not_appear'] == 1)
    check('  and leaves offense_pct at zero for a known non-appearance',
          r['offense_pct'] == 0.0)
    r2 = B.synthetic_row(2026, 1, 'KC', '00-0000000', 'WR', cols, None)
    check('  while an unplayed game carries None, never 0',
          r2['did_not_appear'] is None and r2['offense_pct'] is None)
    check('  and the ordinal is season*100 + week',
          r2['ord'] == 202601, str(r2['ord']))


# ======================================================== D. chronology
def test_the_fit_trains_on_strictly_earlier_seasons():
    o = B.fit(2025)
    if o.state is not State.PASS:
        blocked('the 2025 fit', f'{o.code}: {o.detail[:120]}')
        return
    ts = o.evidence['train_seasons']
    check('no training season is the forecast season or later',
          max(ts) < 2025, str(ts))
    check('  the reliability constant is cut at the season start',
          o.evidence['k_evidence']['cut'] == 202500,
          str(o.evidence['k_evidence']['cut']))
    check('  k is estimated, not chosen',
          o.evidence['k_evidence'].get('estimated_not_chosen') is True)
    check('  every training row carries a block',
          o.evidence['v1_presence_rate_in_training'] == 1.0)
    check('  and the fit has 76 features, not 77',
          o.evidence['n_features'] == B.N_FEATURES,
          str(o.evidence['n_features']))


def test_chronology_is_a_refusal_not_a_filter():
    src = inspect.getsource(B._prospective_union)
    check('the serve walk refuses history at or after the target week',
          'B_HISTORY_NOT_STRICTLY_EARLIER' in src)
    check('  and truncates only under an explicit replay flag',
          'replay' in inspect.signature(B._prospective_union).parameters
          and 'if late and not replay' in src)
    fsrc = inspect.getsource(B.fit)
    check('  and the fit names leakage rather than dropping it',
          'B_TRAINING_LEAKAGE' in fsrc)


def test_this_game_s_snap_share_is_never_a_feature():
    """It was one, for exactly one run, and scored 0.04101 in-sample."""
    src = inspect.getsource(B.predict)
    check("predict sets this game's snap share to None",
          "r['snap'] = None" in src)
    check('  and says why in the line above it',
          'unknown before the game is played' in src)


# ================================================== E. the arm switch
def test_the_default_arm_is_the_incumbent():
    o = AA.resolve()
    check('resolve() with no argument returns the incumbent',
          o.state is State.PASS and o.value['arm'] == AA.INCUMBENT_KNOWN_DEFECTIVE,
          str(o)[:120])
    check('  and the incumbent declaration names its own defect',
          'presence' in (o.value.get('known_defect') or ''))
    check('  DEFAULT_ARM is the incumbent in the source too',
          AA.DEFAULT_ARM == AA.INCUMBENT_KNOWN_DEFECTIVE)


def test_confirmed_and_promoted_refuse():
    for arm in (AA.CANDIDATE_B_CONFIRMED, AA.CANDIDATE_B_PROMOTED):
        o = AA.resolve(arm)
        check(f'{arm} is BLOCKED, not runnable',
              o.state is State.BLOCKED, str(o)[:120])
        check(f'  and the cause is GOVERNANCE, a decision not a defect',
              o.evidence.get('cause') == Cause.GOVERNANCE.value,
              str(o.evidence.get('cause')))
        check(f'  with a reason, not a bare refusal',
              len(o.detail) > 80, o.detail[:80])


def test_live_evaluation_runs_and_is_not_promoted():
    o = AA.resolve(AA.CANDIDATE_B_LIVE_EVALUATION)
    check('the live-evaluation arm resolves', o.state is State.PASS, str(o)[:120])
    check('  to appearance_b', o.value['module'].endswith('appearance_b'))
    check('  and its governance says NOT promoted',
          'NOT promoted' in o.value['governance'], o.value['governance'])
    check('  and it declares its own residual limit',
          '53-man roster' in (o.value.get('known_defect') or ''))


def test_the_switch_never_falls_back():
    """THE GUARD. A fallback runs an unrequested model behind a requested name."""
    o = AA.resolve('r8')
    check('an unrecognised arm FAILS', o.state is State.FAIL, str(o)[:120])
    check('  and does not quietly return the default',
          o.value is None and 'APPEARANCE_ARM_UNKNOWN' == o.code)
    src = inspect.getsource(AA.predict)
    check('  and predict returns the arm\'s own refusal unchanged',
          'return o' in src and 'except' not in src)
    check('  with no second arm tried',
          src.count('mod.predict') == 1, str(src.count('mod.predict')))


def test_every_row_carries_the_arm_that_produced_it():
    src = inspect.getsource(AA.predict)
    for key in ('appearance_arm', 'appearance_spec_version',
                'appearance_coef_sha256', 'appearance_module_sha256',
                'appearance_arm_governance'):
        check(f'  each row carries {key}', f"'{key}'" in src, key)
    check('  the per-player value is a dict, not a bare float',
          "'p_appear': float(p)" in src)
    o = AA.module_identity(AA.CANDIDATE_B_LIVE_EVALUATION)
    check('  and the module hash is read from the file that would run',
          o.state is State.PASS
          and o.value['path'] == 'nfl/production/nonqb/appearance_b.py',
          str(o)[:120])


def test_an_out_of_range_probability_is_refused():
    src = inspect.getsource(AA.predict)
    check('the switch range-checks what the arm returned',
          'APPEARANCE_ARM_PROBABILITY_OUT_OF_RANGE' in src)
    check('  and refuses an empty PASS as an absence',
          'APPEARANCE_ARM_EMPTY' in src)


# ================================================== F. the untouched files
def test_layers_py_is_untouched():
    """THE GUARD. Q9's frozen candidate identity hashes this file."""
    p = _REPO / 'nfl/production/nonqb/layers.py'
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    check('layers.py still hashes to Q9\'s frozen identity',
          got.startswith(Q9_LAYERS_SHA16), got[:16])
    ly = p.read_text()
    check('  and it knows nothing about Candidate B',
          'appearance_b' not in ly and 'appearance_arm' not in ly)
    for mod in ('appearance_b', 'appearance_arm'):
        src = (_REPO / f'nfl/production/nonqb/{mod}.py').read_text()
        check(f'  and {mod}.py does not import layers',
              'import layers' not in src and 'nonqb import layers' not in src)


def test_the_incumbent_module_is_read_only():
    src = (_REPO / 'nfl/production/nonqb/appearance_b.py').read_text()
    for bad in ('R8.featurise =', 'R8.predict =', 'R8.V1_NUMERIC =',
                'R8._ENRICHED', 'setattr(R8', 'AM._walk ='):
        check(f'  appearance_b never rebinds {bad.rstrip(" =")}',
              bad not in src, bad)


def test_the_preregistration_is_cited_by_hash():
    check('appearance_b carries the preregistration hash',
          B.PREREG_SHA256 == 'b14738a0a4a262cccba416b6d76e3b80'
                             'db4340b46f1ab144d0546bfe8f368dda',
          B.PREREG_SHA256)
    p = _REPO / 'nfl/research/remediation/ws_a/PREREG_appearance_leak.md'
    if not p.exists():
        blocked('the preregistration file', f'{p} is absent')
        return
    check('  and the file on disk still hashes to it',
          hashlib.sha256(p.read_bytes()).hexdigest() == B.PREREG_SHA256)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            print(name)
            fn()
    tail = f', {BLOCKED} blocked' if BLOCKED else ''
    print(f'\n{PASSED} passed, {FAILED} failed{tail}')
    sys.exit(1 if FAILED else 0)
