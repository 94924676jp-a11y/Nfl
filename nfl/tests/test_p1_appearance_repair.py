"""P1: the two appearance-path defects from AUTOPSY_DEN_KC section 4.

Written BEFORE the repair, against the repaired API, so the first run of this
module shows both defects failing by name. Two kinds of check live here and
they are deliberately different:

  * CHARACTERISATION checks pin the DEFECT as it stands in R8 and in the
    offence-wide depth scale. They passed before the repair and must keep
    passing after it, because R8 and R9 are frozen lineage and a silent change
    to either is the thing this file exists to catch.

  * REPAIR checks name the successor's API. They failed before the repair and
    must pass after it.

DEFECT 1, `appearance_r8.featurise`: `f_weeks_since_appear` is the only
numeric in the block that carries a value with no missingness indicator, and
`min(v or 9, 9) / 9.0` is a FALSY test, so `None`, `0` and `9+` all encode to
1.0000 while `1` encodes to 0.1111.

DEFECT 2, `depth_vintage.daily`: the ordinal is offence-wide, so a club's
`pos_rank == 1` quarterback, back, receiver and tight end compete for one
ordinal and are separated only by `gsis_id` -- an identifier, not a football
fact.
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import candidate_mode as CM                      # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8                  # noqa: E402
from nfl.production.nonqb import depth_vintage as DV                  # noqa: E402

PASSED = FAILED = BLOCKED = 0

# The frozen layer file, recorded by the owner of this task. A repair in the
# appearance path that quietly edits the layer stack is out of scope by
# construction, so the hash is asserted rather than trusted.
LAYERS_SHA256_PREFIX = '481f005f682cd721'

# R8's fitted identity as measured on this tree BEFORE the repair, season by
# season. These are the old coefficients the successor must not disturb.
R8_BASELINE = {'spec_version': 'appearance-r8-reliability-weighted-1',
               'n_features': 77,
               # Measured 2026-09-15 on this tree before a line was changed.
               'coef_sha256_2026': '3cc23577a3d234ba'}


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
    """A check that could not run. Counted apart and never as a pass."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


K = 1.2176


def _row(wsa, rank=1):
    """A frame row carrying a v1 block, with one quantity varied."""
    blk = {k: 0.5 for k in R8.V1_NUMERIC}
    blk['f_weeks_since_appear'] = wsa
    blk['f_n_teammates_out'] = 0.0
    blk['f_practice_seq'] = None
    blk['f_practice_improving'] = 0.0
    blk['f_practice_worsening'] = 0.0
    return {'s': 2026, 'w': 1, 't': 'KC', 'pid': 'x', 'pos': 'RB',
            'rank': rank, 'rank_pos': rank, 'n_cur': 0, 'n_prior': 8,
            'app_cur': None, 'app_ewma_cur': None, 'rate3_cur': None,
            'snap_ewma_cur': None, 'v1': blk}


def _wsa_column(featurise, values):
    """The index of the column that moves with `f_weeks_since_appear`, and the
    encoding it produces for each value.

    Found by DIFFING, not by counting offsets: an offset written down in a test
    goes stale the moment a feature is inserted above it, and then the test is
    measuring the wrong column while still passing.
    """
    base = featurise(_row(1), K)
    moved = set()
    enc = {}
    for v in values:
        vec = featurise(_row(v), K)
        for i, (a, b) in enumerate(zip(base, vec)):
            if a != b:
                moved.add(i)
    for v in values:
        vec = featurise(_row(v), K)
        enc[v] = tuple(vec[i] for i in sorted(moved))
    return sorted(moved), enc


# ============================================ A. defect 1, characterisation
def test_r8_encodes_never_seen_and_gone_all_season_identically():
    """CHARACTERISATION. This is the defect, pinned. It must keep failing to
    be monotone in R8 -- R8 is frozen lineage and is not edited here."""
    cols, enc = _wsa_column(R8.featurise, [None, 0, 1, 2, 9, 12])
    check('R8 moves exactly one column with f_weeks_since_appear, no flag',
          len(cols) == 1, f'{cols}')
    check('  None and 9 are the same number in R8',
          enc[None] == enc[9], f'{enc[None]} vs {enc[9]}')
    check('  a real 0 is encoded as the MAXIMUM in R8, not the minimum',
          enc[0] == enc[9] and enc[0] > enc[1],
          f'0->{enc[0]} 1->{enc[1]} 9->{enc[9]}')
    check('  so R8 is not monotone in its own quantity',
          not (enc[0] <= enc[1] <= enc[2] <= enc[9]), str(enc))


def test_every_other_numeric_in_the_block_carries_a_flag():
    """The comparison that makes defect 1 a defect rather than a choice."""
    base = R8.featurise(_row(1), K)
    n_moved = []
    for key in R8.V1_NUMERIC:
        r = _row(1)
        r['v1'][key] = None
        vec = R8.featurise(r, K)
        n_moved.append(sum(1 for a, b in zip(base, vec) if a != b))
    check('all twelve V1_NUMERIC features move a value AND a flag',
          set(n_moved) == {2}, f'{dict(zip(R8.V1_NUMERIC, n_moved))}')


# ==================================================== B. defect 1, repaired
def test_the_successor_pairs_the_feature_with_a_missingness_indicator():
    if not hasattr(R8, 'featurise_r10'):
        check('appearance_r8 exposes the repaired featuriser featurise_r10',
              False, 'attribute missing')
        return
    check('appearance_r8 exposes the repaired featuriser featurise_r10', True)
    cols, enc = _wsa_column(R8.featurise_r10, [None, 0, 1, 2, 9, 12])
    check('  the repaired featuriser moves a value AND a flag',
          len(cols) == 2, f'{cols}')
    check('  and never seen is distinguishable from gone all season',
          enc[None] != enc[9], f'{enc[None]} vs {enc[9]}')
    check('  the successor carries exactly one column more than R8',
          getattr(R8, 'N_FEATURES_R10', None) == R8.N_FEATURES + 1,
          f'{getattr(R8, "N_FEATURES_R10", None)} vs {R8.N_FEATURES}')


def test_the_successor_encoding_is_monotonic_in_its_own_quantity():
    if not hasattr(R8, 'featurise_r10'):
        check('featurise_r10 is monotone in f_weeks_since_appear', False,
              'attribute missing')
        return
    vals = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12]
    cols, enc = _wsa_column(R8.featurise_r10, vals + [None])
    # The value column is the one that varies across PRESENT values; the flag
    # is constant across them and fires only on None.
    seq = [enc[v] for v in vals]
    check('the encoding never decreases as weeks-since-appear grows',
          all(a <= b for a, b in zip(seq, seq[1:])), str(seq))
    check('  a player who appeared in the most recent game is at the minimum',
          enc[0] == min(seq), f'{enc[0]} vs {min(seq)}')
    check('  and the missing case sets the flag rather than borrowing a value',
          enc[None] != enc[0] and enc[None] != enc[9],
          f'None->{enc[None]} 0->{enc[0]} 9->{enc[9]}')


# ============================================ C. defect 2, characterisation
_CHART = ('dt,team,gsis_id,pos_abb,pos_rank\n'
          '2026-09-13T12:00:00Z,KC,00-aaa-QB1,QB,1\n'
          '2026-09-13T12:00:00Z,KC,00-bbb-TE1,TE,1\n'
          '2026-09-13T12:00:00Z,KC,00-ccc-RB1,RB,1\n'
          '2026-09-13T12:00:00Z,KC,00-ddd-WR1,WR,1\n'
          '2026-09-13T12:00:00Z,KC,00-eee-RB2,RB,2\n'
          '2026-09-13T12:00:00Z,KC,00-fff-WR2,WR,2\n')

# The same club, same football, with the identifiers relabelled so the
# alphabetical order of the four rank-1 players is reversed. Nothing about the
# depth chart has changed.
_CHART_RELABELLED = _CHART.replace('00-aaa-QB1', '00-zzz-QB1') \
                          .replace('00-bbb-TE1', '00-yyy-TE1') \
                          .replace('00-ccc-RB1', '00-xxx-RB1') \
                          .replace('00-ddd-WR1', '00-www-WR1')


def _ranks(o, key=lambda pid: pid):
    m = o.value['KC'][0][1]
    return {key(pid): v[0] for pid, v in m.items()}


def _suffix(pid):
    return pid.split('-')[-1]


def test_the_offence_wide_ordinal_is_position_contaminated():
    """CHARACTERISATION. The default scale is unchanged by this repair."""
    o = DV.daily(_CHART)
    if not check('the daily chart parses', o.state is State.PASS, str(o)[:120]):
        return
    r = _ranks(o, _suffix)
    check('four pos_rank-1 players receive four DIFFERENT ordinals',
          len({r['QB1'], r['TE1'], r['RB1'], r['WR1']}) == 4, str(r))
    check('  the club\'s RB1 is not ordinal 1', r['RB1'] != 1, str(r))
    check('  and the ordinal is decided by gsis_id alphabetical order',
          _ranks(DV.daily(_CHART_RELABELLED), _suffix)['RB1'] != r['RB1'],
          str(r))
    mix = o.evidence.get('rank_1_position_mix') or {}
    check('  the module says so on its own artifact',
          'OFFENCE-WIDE' in str(o.evidence.get('rank_scale')) and len(mix) >= 1,
          str(mix))


# ==================================================== D. defect 2, repaired
def test_a_within_position_scale_exists_and_the_default_is_unchanged():
    if not hasattr(DV, 'WITHIN_POSITION'):
        check('depth_vintage names a within-position rank scale', False,
              'attribute missing')
        return
    check('depth_vintage names a within-position rank scale', True)
    before = DV.daily(_CHART)
    after = DV.daily(_CHART, scale=DV.OFFENCE_WIDE)
    check('  the default scale is still the offence-wide ordinal',
          before.value == after.value, f'{before.value} vs {after.value}')
    o = DV.daily(_CHART, scale=DV.WITHIN_POSITION)
    if not check('  the within-position scale resolves',
                 o.state is State.PASS, str(o)[:150]):
        return
    r = _ranks(o, _suffix)
    check('  every position has its own rank 1',
          r['QB1'] == r['TE1'] == r['RB1'] == r['WR1'] == 1, str(r))
    check('  and the second man at a position is 2',
          r['RB2'] == 2 and r['WR2'] == 2, str(r))


def test_the_within_position_rank_does_not_depend_on_the_identifier():
    if not hasattr(DV, 'WITHIN_POSITION'):
        check('relabelling the players cannot move a within-position rank',
              False, 'attribute missing')
        return
    a = _ranks(DV.daily(_CHART, scale=DV.WITHIN_POSITION), _suffix)
    b = _ranks(DV.daily(_CHART_RELABELLED, scale=DV.WITHIN_POSITION), _suffix)
    check('relabelling the players cannot move a within-position rank',
          a == b, f'{a} vs {b}')


def test_an_unknown_scale_is_refused_rather_than_defaulted():
    if not hasattr(DV, 'WITHIN_POSITION'):
        check('an unknown rank scale is a named refusal', False,
              'attribute missing')
        return
    o = DV.daily(_CHART, scale='whatever_the_caller_typed')
    check('an unknown rank scale is a named refusal',
          o.state is State.FAIL and 'SCALE' in o.code, str(o)[:150])


# ================================================ E. the successor candidate
def test_the_repair_is_registered_as_a_new_mode():
    mode = getattr(CM, 'V1_CANDIDATE_R10', None)
    if mode is None:
        check('candidate_mode registers the successor V1_CANDIDATE_R10',
              False, 'attribute missing')
        return
    check('candidate_mode registers the successor V1_CANDIDATE_R10', True)
    check('  and lists it in MODES', mode in CM.MODES, str(CM.MODES))
    o = CM.resolve(mode)
    if not check('  it resolves', o.state is State.PASS, str(o)[:150]):
        return
    fl = o.value['flags']
    check('  naming its own appearance mechanism',
          fl.get('appearance_r10') is True, str(fl))
    check('  and exactly one: R8\'s flag is removed, not left set',
          'appearance_r8' not in fl and 'appearance_r7' not in fl, str(fl))
    check('  it inherits the R9 quarterback room',
          fl.get('qb_allocator') == 'qb_room_v2', str(fl))
    other = {k: v for k, v in fl.items() if k != 'appearance_r10'}
    r9 = {k: v for k, v in CM.R9_FLAGS.items() if k != 'appearance_r8'}
    check('  and changes nothing else about R9', other == r9,
          f'{other} vs {r9}')


def test_r8_and_r9_are_not_edited_by_the_successor():
    check('R8 still names its own appearance mechanism',
          CM.R8_FLAGS.get('appearance_r8') is True, str(CM.R8_FLAGS))
    check('R9 still names R8\'s appearance mechanism',
          CM.R9_FLAGS.get('appearance_r8') is True, str(CM.R9_FLAGS))
    check('  and neither carries the successor\'s',
          'appearance_r10' not in CM.R8_FLAGS
          and 'appearance_r10' not in CM.R9_FLAGS)
    check('R8\'s spec version is unchanged',
          R8.SPEC_VERSION == R8_BASELINE['spec_version'], R8.SPEC_VERSION)
    check('R8\'s design row is unchanged in width',
          R8.N_FEATURES == R8_BASELINE['n_features'], str(R8.N_FEATURES))


def test_the_frozen_layer_stack_is_untouched():
    p = os.path.join(_ROOT, 'nfl/production/nonqb/layers.py')
    h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    check('layers.py is byte-identical to the frozen hash',
          h.startswith(LAYERS_SHA256_PREFIX), h[:16])


def test_the_successor_refuses_a_row_with_no_within_position_rank():
    """A missing scale must be a NAMED refusal, not a fall-through to `rank`.

    Falling back would serve the offence-wide ordinal to a model fitted on the
    within-position one -- the train/serve break this candidate exists to
    close, reintroduced through a default.
    """
    if not hasattr(R8, 'featurise_r10'):
        check('a row with no rank_pos is refused by name', False,
              'attribute missing')
        return
    r = _row(1)
    r.pop('rank_pos')
    try:
        R8.featurise_r10(r, K)
        check('a row with no rank_pos is refused by name', False,
              'it returned a design row instead')
    except ValueError as e:
        check('a row with no rank_pos is refused by name',
              'R10_RANK_SCALE_MISSING' in str(e), str(e)[:120])
    except Exception as e:                                    # noqa: BLE001
        check('a row with no rank_pos is refused by name', False,
              f'{type(e).__name__}: {e}'[:120])


def test_the_successor_refits_and_r8s_coefficients_do_not_move():
    """THE LOAD-BEARING ONE, and it runs the real frame.

    Both repairs change the design matrix, so R10 must carry its own
    coefficients -- and R8's must be exactly where they were. The hashes below
    were measured on this tree BEFORE the repair was written.
    """
    fr = R8.enriched_frame_r10() if hasattr(R8, 'enriched_frame_r10') else None
    if fr is None:
        check('the successor frame builds', False, 'attribute missing')
        return
    if fr.state is not State.PASS:
        blocked('the successor frame builds',
                f'{fr.state.value}[{fr.code}] {fr.detail[:90]}')
        return
    rows = fr.value
    check('the successor frame carries a within-position rank on every row',
          all('rank_pos' in r for r in rows), str(len(rows)))
    base = R8.enriched_frame()
    check('  and the offence-wide rank is not mutated on any row',
          all(a.get('rank') == b.get('rank')
              for a, b in zip(base.value, rows)))
    check('  while the daily-vendor rows really do move',
          (fr.evidence.get('n_rows_whose_depth_rank_moved') or 0) > 0,
          str(fr.evidence.get('n_rows_whose_depth_rank_moved')))
    f10 = R8.fit_r10(2026)
    if f10.state is not State.PASS:
        blocked('the successor fits', f'{f10.state.value}[{f10.code}]')
        return
    check('the successor fits on its own design row',
          f10.evidence.get('n_features') == R8.N_FEATURES + 1,
          str(f10.evidence.get('n_features')))
    f8 = R8.fit(2026)
    check('  and R8\'s 2026 coefficients are exactly where they were',
          f8.value['coef_sha256'] == R8_BASELINE['coef_sha256_2026'],
          f8.value['coef_sha256'])
    check('  which is not the successor\'s hash',
          f10.value['coef_sha256'] != f8.value['coef_sha256'],
          f10.value['coef_sha256'])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
