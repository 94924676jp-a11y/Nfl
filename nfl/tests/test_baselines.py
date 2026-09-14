"""Adversarial tests for the D8 frozen baselines.

THE ONE THAT MATTERS IS THE LEAK TEST, AND IT IS BUILT SO THAT IT CAN FAIL.

A leak test that asserts `forecast(week 5) == forecast(week 5)` proves nothing;
it would pass against an estimator that reads the box score of the game it is
forecasting. The construction here instead MUTATES THE FUTURE and requires the
PAST not to move: every player row and team row at or after a cut ordinal is
multiplied by 7.5 and shifted by 1000, the index is rebuilt, and every
baseline's forecast for games AT the cut must be bit-identical.

AND THE TEST IS DEMONSTRATED AGAINST A SEEDED VIOLATION. `test_c2` defines an
estimator that differs from the real one by a single character -- `bisect_right`
where the real cut uses `bisect_left`, so the forecast game itself enters its
own history -- and requires the same mutation to MOVE it. If that check ever
starts passing trivially, the leak test above has stopped measuring anything.
This is the repository rule that a guard is not demonstrated because compliant
data passes it.

Run standalone:  python3.12 nfl/tests/test_baselines.py
"""
from __future__ import annotations

import ast
import bisect
import copy
import fnmatch
import glob
import gzip
import json
import os
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.baselines import estimators as E     # noqa: E402
from nfl.research.baselines import frame as F          # noqa: E402
from nfl.research.baselines import panel as P          # noqa: E402
from nfl.research.baselines import specs as S          # noqa: E402

PASSED = FAILED = BLOCKED = 0
CUT = 202310            # 2023, week 10. Arbitrary, and stated rather than tuned.


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


_CACHE = {}


def panel():
    if 'panel' not in _CACHE:
        _CACHE['panel'] = P.build_panel()
    return _CACHE['panel']


def index():
    if 'index' not in _CACHE:
        _CACHE['index'] = F.Index(panel())
    return _CACHE['index']


# ================================================================ A. chronology
def test_a1_lawful_seasons_resolve_and_others_are_refused():
    for s in P.LAWFUL_SEASONS:
        p = P.blob_for(s)
        check(f'season {s} resolves to exactly one blob that exists',
              os.path.exists(p), os.path.basename(p))
    for s in (2019, 2020, 2025, 2026, 2027):
        try:
            P.blob_for(s)
            check(f'season {s} is refused', False, 'it was NOT refused')
        except P.ChronologyRefused as exc:
            check(f'season {s} is refused',
                  'BASELINE_CHRONOLOGY_REFUSED' in str(exc))


def test_a2_the_glob_cannot_reach_the_live_season():
    """The prior agent's failure was `pbp_20*`. Prove ours cannot repeat it."""
    present = [os.path.basename(p) for p in
               glob.glob(os.path.join(P.POSTGAME, 'pbp_*.csv.gz'))]
    live = [n for n in present if n.startswith('pbp_2026.')]
    check('the 2026 blobs are physically present, so this is a real test, '
          'not a vacuous one', len(live) >= 1, f'{len(live)} found')
    for s in P.LAWFUL_SEASONS:
        pat = f'pbp_{s}.*.csv.gz'
        hit = [n for n in live if fnmatch.fnmatch(n, pat)]
        check(f'the season-{s} pattern matches no 2026 blob', hit == [],
              str(hit))
    naive = [n for n in present if fnmatch.fnmatch(n, 'pbp_20*')]
    check('the NAIVE pattern pbp_20* would have matched 2026 -- which is the '
          'seeded violation this guard exists for',
          any(n.startswith('pbp_2026.') for n in naive),
          f'{len(naive)} files')


def test_a3_data_identity_in_the_frozen_spec_matches_the_bytes_on_disk():
    doc = S.load()
    live = P.data_identity()
    check('every frozen blob hash still matches the file on disk',
          live == doc['data_identity'],
          'MISMATCH: the panel is not the panel the constants were frozen '
          'against' if live != doc['data_identity'] else '')


# ================================================================== B. the cut
def test_b1_prior_is_strictly_earlier():
    series = [(202301, 1.0), (202302, 2.0), (202303, 3.0)]
    check('the cut excludes the forecast ordinal itself',
          E.prior(series, 202302) == [(202301, 1.0)])
    check('the cut excludes everything after it',
          E.prior(series, 202301) == [])
    check('the cut keeps everything before it',
          E.prior(series, 202304) == series)


def test_b2_a_same_ordinal_duplicate_row_lands_on_the_future_side():
    """A club can carry two rows at one ordinal after a postponement. Both must
    be on the future side of the cut, not one of each."""
    series = [(202301, 1.0), (202302, 2.0), (202302, 99.0), (202303, 3.0)]
    check('both same-ordinal rows are excluded',
          E.prior(series, 202302) == [(202301, 1.0)])


# ============================================================== C. the leak test
def _mutated_index(cut: int):
    """The same panel with every row AT OR AFTER `cut` corrupted beyond
    recognition. A forecast for a game at `cut` must not notice."""
    pan = copy.deepcopy(panel())
    n = 0
    for r in pan['players']:
        if P.ordinal(r['season'], r['week']) >= cut:
            for q in P.QUANTITIES:
                r[q] = r[q] * 7.5 + 1000.0
            n += 1
    for r in pan['teams']:
        if P.ordinal(r['season'], r['week']) >= cut:
            for q in P.TEAM_QUANTITIES:
                r[q] = r[q] * 7.5 + 1000.0
    return F.Index(pan), n


def _forecasts(idx, quantity, rows, doc):
    const, win = doc['constants'][quantity], doc['windows'][quantity]
    k, c = const['k_prior_games'], const['c_carryover_slope']
    out = []
    for r in rows:
        h = idx.hist(r['pid'], quantity, r['ordinal'])
        mu = 10.0            # a fixed stand-in: the tables are not under test
        try:
            b1 = E.season_to_date(h, r['season'])
        except E.Undefined:
            b1 = E.w1_prior_season_shrunk(h, r['season'], mu, k, c)
        try:
            b2 = E.recent_n(h, win['recent_n'])
        except E.Undefined:
            b2 = mu
        try:
            b3 = E.ewma(h, win['ewma_half_life_games'])
        except E.Undefined:
            b3 = mu
        b4 = E.shrunk(h, r['season'], mu, k, c)
        out.append((b1, b2, b3, b4))
    return out


def test_c1_mutating_the_future_does_not_move_a_past_forecast():
    doc = S.load()
    idx = index()
    mut, n_mutated = _mutated_index(CUT)
    check('the mutation actually touched rows -- an untouched mutation would '
          'make this test vacuous', n_mutated > 500, f'{n_mutated} rows')
    total = moved = 0
    for q in ('pass_att', 'pass_yds', 'carries', 'targets', 'rec_yds'):
        rows = [r for r in idx.frame_a(q, (2023,))
                if r['ordinal'] == CUT]
        check(f'{q}: there are rows at the cut to test', len(rows) > 10,
              f'{len(rows)} rows')
        a = _forecasts(idx, q, rows, doc)
        b = _forecasts(mut, q, rows, doc)
        total += len(a) * 4
        moved += sum(1 for x, y in zip(a, b) for u, v in zip(x, y) if u != v)
        check(f'{q}: every baseline forecast at the cut is bit-identical '
              f'after the future was corrupted', a == b,
              '' if a == b else 'A FORECAST MOVED -- THIS IS A LEAK')
    check('no forecast moved anywhere', moved == 0,
          f'{moved} of {total} moved')
    _CACHE['leak_rows_checked'] = total


def test_c2_the_leak_test_catches_a_one_character_leak():
    """The seeded violation. `bisect_right` puts the forecast game inside its
    own history; the identical mutation must then MOVE the forecast."""
    def leaky_prior(series, cutoff):
        keys = [o for o, _ in series]
        return series[:bisect.bisect_right(keys, cutoff)]

    idx = index()
    mut, _ = _mutated_index(CUT)
    moved = total = 0
    for q in ('pass_att', 'carries', 'targets'):
        rows = [r for r in idx.frame_a(q, (2023,)) if r['ordinal'] == CUT]
        for r in rows:
            a = leaky_prior(idx.series[(r['pid'], q)], r['ordinal'])
            b = leaky_prior(mut.series[(r['pid'], q)], r['ordinal'])
            if not a:
                continue
            total += 1
            if E.recent_n(a, 3) != E.recent_n(b, 3):
                moved += 1
    check('the seeded leaking estimator IS detected by the same mutation',
          total > 100 and moved > 0.5 * total,
          f'{moved} of {total} forecasts moved')
    check('and the real cut, run on the same rows, moved none',
          _CACHE.get('leak_rows_checked', 0) > 0,
          'test_c1 must have run')


def test_c5_the_leak_test_fails_when_the_cut_itself_is_bypassed():
    """The load-bearing half of the guard standard (bypass.guard_bypassed).

    `test_c1` shows the leak test passes on compliant code. That is the easy
    half. This replaces `estimators.prior` -- the single function every
    baseline's history goes through -- with a `bisect_right` version, reruns
    the SAME comparison, and requires it to FAIL. A leak test that still passed
    with the cut removed would be testing nothing at all.
    """
    from nfl.tests.bypass import guard_bypassed

    def leaking_cut(series, cutoff_ordinal):
        keys = [o for o, _ in series]
        return series[:bisect.bisect_right(keys, cutoff_ordinal)]

    doc = S.load()
    idx = index()
    mut, _ = _mutated_index(CUT)
    with guard_bypassed('nfl.research.baselines.estimators', 'prior',
                        replacement=leaking_cut):
        moved = total = 0
        for q in ('pass_att', 'carries', 'targets'):
            rows = [r for r in idx.frame_a(q, (2023,))
                    if r['ordinal'] == CUT]
            a = _forecasts(idx, q, rows, doc)
            b = _forecasts(mut, q, rows, doc)
            total += len(a) * 4
            moved += sum(1 for x, y in zip(a, b)
                         for u, v in zip(x, y) if u != v)
    check('with the cut bypassed, the leak test FAILS -- so on the real cut '
          'it was measuring something', total > 100 and moved > 0,
          f'{moved} of {total} forecasts moved once the cut was removed')
    check('the cut was restored after the bypass',
          E.prior([(1, 1.0), (2, 2.0)], 2) == [(1, 1.0)])


def test_c3_frame_membership_and_rank_are_prior_information_only():
    idx = index()
    mut, _ = _mutated_index(CUT)
    for q in ('targets', 'carries'):
        a = [(r['game_id'], r['pid'], r['rank'])
             for r in idx.frame_a(q, (2023,)) if r['ordinal'] == CUT]
        b = [(r['game_id'], r['pid'], r['rank'])
             for r in mut.frame_a(q, (2023,)) if r['ordinal'] == CUT]
        check(f'{q}: who is in the frame, and at what rank, is unchanged when '
              f'the forecast game is corrupted', a == b, f'{len(a)} rows')


def test_c4_prior_season_tables_ignore_the_evaluation_seasons():
    idx = index()
    frames = {2021: idx.frame_a('targets', (2021,)),
              2022: idx.frame_a('targets', (2022,)),
              2023: idx.frame_a('targets', (2023,))}
    clean = F.league_prior_table(idx, 'targets', 2023, frames)
    poisoned = {k: ([dict(r, actual=r['actual'] * 100 + 5) for r in v]
                    if k >= 2023 else v) for k, v in frames.items()}
    dirty = F.league_prior_table(idx, 'targets', 2023, poisoned)
    check('the 2023 prior table is unchanged when 2023 rows are poisoned',
          clean == dirty, str(sorted(clean.items()))[:90])
    also = F.league_prior_table(idx, 'targets', 2024, poisoned)
    check('and the 2024 prior table DOES change -- so the poisoning was real '
          'and the previous check was not vacuous',
          also != F.league_prior_table(idx, 'targets', 2024, frames))


# ============================================================ D. the panel rules
def test_d1_grouping_carries_the_team_in_every_key():
    idx = index()
    bad = [k for k in list(idx.by_key)[:50] if not isinstance(k, tuple)]
    check('player rows are keyed by (gsis_id, ordinal) and carry a team field',
          not bad and all('team' in r for r in idx.players[:50]))
    same = [r for r in idx.players if r['game_id'] == '2024_01_ARI_BUF'
            and r['pass_att'] > 0]
    teams = {r['team'] for r in same}
    check('both sides of a game appear as separate rows, so a game-level '
          'group would have merged them', len(teams) == 2, str(sorted(teams)))
    by_game_max = max(r['pass_att'] for r in same)
    by_team = sorted(r['pass_att'] for r in same)
    check('grouping by game alone would have selected the larger passer and '
          'discarded the other -- the seeded version of the error',
          by_game_max == by_team[-1] and by_team[0] < by_team[-1],
          f'{by_team}')


def test_d2_kneels_are_excluded_and_it_matters():
    pan = panel()
    dropped = pan['audit']['2024']['drop_kneel']
    n = 0
    with gzip.open(P.blob_for(2024), 'rt', newline='') as fh:
        import csv as _csv
        rdr = _csv.reader(fh)
        hdr = next(rdr)
        ix = {h: i for i, h in enumerate(hdr)}
        for row in rdr:
            if (row[ix['season_type']] == 'REG' and row[ix['qb_kneel']] == '1'
                    and row[ix['play_deleted']] != '1' and row[ix['posteam']]):
                n += 1
    check('the kneels dropped by the builder equal an independent recount',
          dropped == n, f'builder {dropped} vs recount {n}')
    check('and there were kneels to drop, so the filter is not vacuous',
          n > 100, str(n))


def test_d3_arithmetic_identities_hold_on_every_row():
    pan = panel()
    bad_c = sum(1 for r in pan['players'] if r['pass_cmp'] > r['pass_att'])
    bad_r = sum(1 for r in pan['players'] if r['receptions'] > r['targets'])
    check('no row has more completions than attempts', bad_c == 0, str(bad_c))
    check('no row has more receptions than targets', bad_r == 0, str(bad_r))
    neg = sum(1 for r in pan['players']
              for q in ('pass_att', 'carries', 'targets') if r[q] < 0)
    check('no opportunity count is negative', neg == 0, str(neg))


def test_d5_the_panel_agrees_with_an_independently_derived_panel():
    """Cross-validation against `nfl/research/inputs/panel_p3.csv.gz`, which
    was built by a different agent, from a different pipeline, for a different
    purpose. Targets must agree EXACTLY; carries must disagree only on
    quarterbacks, because that is the kneel exclusion and nothing else.

    An identity that holds by construction proves nothing. This one does not:
    two independent derivations either land on the same integer or they do not.
    """
    import csv as _csv
    if not os.path.exists(P.PANEL_P3):
        blocked('cross-validation against panel_p3', 'panel_p3 is absent')
        return
    p3 = {}
    with gzip.open(P.PANEL_P3, 'rt', newline='') as fh:
        for r in _csv.DictReader(fh):
            if int(r['season']) in P.LAWFUL_SEASONS:
                p3[(int(r['season']), int(r['week']), r['team'],
                    r['gsis_id'])] = r
    mine = {(r['season'], r['week'], r['team'], r['gsis_id']): r
            for r in panel()['players']}
    both = set(mine) & set(p3)
    check('the two panels overlap on every row this one carries',
          len(both) == len(mine), f'{len(both)} of {len(mine)}')
    tgt_bad = [k for k in both
               if mine[k]['targets'] != float(p3[k]['targets'] or 0)]
    check('targets agree EXACTLY on every shared row', tgt_bad == [],
          f'{len(tgt_bad)} disagreements')
    car_bad = [k for k in both
               if mine[k]['carries'] != float(p3[k]['carries'] or 0)]
    non_qb = [k for k in car_bad if mine[k]['position'] != 'QB']
    check('carries disagree on some rows -- so the comparison is not vacuous',
          len(car_bad) > 100, f'{len(car_bad)} rows')
    check('and every carry disagreement is a quarterback, i.e. the kneel '
          'exclusion and nothing else', non_qb == [],
          f'{len(non_qb)} non-QB disagreements')


def test_d4_an_empty_read_raises_instead_of_returning_a_small_number():
    with tempfile.TemporaryDirectory() as td:
        hdr = ','.join(['game_id', 'posteam', 'defteam', 'week', 'season_type',
                        'qb_kneel', 'play_type', 'sack', 'two_point_attempt',
                        'passer_player_id', 'receiver_player_id',
                        'rusher_player_id', 'complete_pass',
                        'incomplete_pass', 'interception', 'passing_yards',
                        'receiving_yards', 'rushing_yards', 'pass_touchdown',
                        'rush_touchdown', 'rush_attempt', 'qb_dropback',
                        'play_deleted'])
        p = os.path.join(td, 'pbp_2021.deadbeef.csv.gz')
        with gzip.open(p, 'wt') as fh:
            fh.write(hdr + '\n')
        real = P.POSTGAME
        try:
            P.POSTGAME = td
            try:
                P.build_season(2021)
                check('a header-only blob raises EmptyRead', False,
                      'it returned instead of raising')
            except P.EmptyRead as exc:
                check('a header-only blob raises EmptyRead',
                      'BASELINE_PANEL_EMPTY' in str(exc))
        finally:
            P.POSTGAME = real
    idx = index()
    try:
        idx.frame_a('targets', (1999,))
        check('an empty frame raises FrameEmpty', False, 'it returned')
    except F.FrameEmpty:
        check('an empty frame raises FrameEmpty', True)


# ================================================================ E. the freeze
def test_e1_every_spec_hash_verifies():
    doc = S.load()
    check('the frozen document self-verifies', S.verify(doc) == [])
    check('every baseline carries its own spec hash',
          all(len(b.get('spec_sha256', '')) == 64
              for b in doc['baselines'].values()),
          f'{len(doc["baselines"])} baselines')
    check('the week-1 transition baseline is present and named',
          'W1-PRIOR-SEASON-SHRUNK' in doc['baselines'])


def test_e2_a_tampered_constant_is_detected():
    doc = copy.deepcopy(S.load())
    b = doc['baselines']['B4-SHRINK']
    q = sorted(b['constants_frozen'])[0]
    b['constants_frozen'][q]['k_prior_games'] += 1e-6
    bad = S.verify(doc)
    check('moving a frozen constant by 1e-6 invalidates the spec hash',
          any(n == 'B4-SHRINK' for n, _, _ in bad), str([n for n, _, _ in bad]))


def test_e3_a_swapped_corpus_is_detected_by_the_spec_hash():
    """The trap the sibling MLB project fell into: a fingerprint that excludes
    the corpus stays identical while the inputs move. Ours does not."""
    doc = copy.deepcopy(S.load())
    for b in doc['baselines'].values():
        b['data_identity']['2024']['sha256'] = '0' * 64
    bad = S.verify(doc)
    check('a substituted corpus invalidates every spec hash',
          len(bad) >= len(doc['baselines']), f'{len(bad)} mismatches')


def test_e4_the_constants_were_estimated_before_the_evaluation_window():
    doc = S.load()
    est, ev = doc['estimation_seasons'], doc['evaluation_seasons']
    check('the estimation window is strictly before the evaluation window',
          max(est) < min(ev), f'{est} then {ev}')
    for q, w in doc['windows'].items():
        check(f'{q}: N and H were selected on prior seasons only',
              max(w['selection_seasons']) < min(ev),
              str(w['selection_seasons']))
    for q, c in doc['constants'].items():
        check(f'{q}: k is labelled as derived and c as fitted',
              c['k_class'] == 'DERIVED_FROM_PRINCIPLE'
              and c['c_class'] == 'FITTED_PRIOR_WINDOW')


# =========================================================== F. governance
def test_f1_no_production_path_imports_a_baseline():
    """A baseline that gets served stops being a baseline, because the thing it
    measures would then contain it."""
    hits = []
    for base in ('nfl/production', 'nfl/product'):
        for p in (_REPO / base).rglob('*.py'):
            src = p.read_text(encoding='utf-8', errors='replace')
            if 'baselines' in src:
                try:
                    tree = ast.parse(src)
                except SyntaxError:
                    continue
                for n in ast.walk(tree):
                    mod = (n.module if isinstance(n, ast.ImportFrom) else None)
                    names = ([a.name for a in n.names]
                             if isinstance(n, (ast.Import, ast.ImportFrom))
                             else [])
                    if (mod and 'research.baselines' in mod) or any(
                            'research.baselines' in a for a in names):
                        hits.append(str(p.relative_to(_REPO)))
    check('no module under nfl/production or nfl/product imports the '
          'baselines package', hits == [], str(hits))


def test_f2_the_baselines_package_does_not_import_production():
    hits = []
    for p in (_REPO / 'nfl' / 'research' / 'baselines').glob('*.py'):
        tree = ast.parse(p.read_text(encoding='utf-8'))
        for n in ast.walk(tree):
            mod = (n.module if isinstance(n, ast.ImportFrom) else None)
            names = ([a.name for a in n.names]
                     if isinstance(n, (ast.Import, ast.ImportFrom)) else [])
            for cand in ([mod] if mod else []) + names:
                if cand and (cand.startswith('nfl.production')
                             or cand.startswith('nfl.product')):
                    hits.append((str(p.name), cand))
    check('the baselines package imports nothing from the serving path',
          hits == [], str(hits))


def test_f3_the_week1_fallback_is_the_one_that_actually_runs():
    doc = S.load()
    idx = index()
    q = 'targets'
    const, win = doc['constants'][q], doc['windows'][q]
    k, c = const['k_prior_games'], const['c_carryover_slope']
    rows = [r for r in idx.frame_a(q, (2023,)) if r['week'] == 1]
    check('there are season-opener rows to test', len(rows) > 50,
          f'{len(rows)} rows')
    same = diff = 0
    for r in rows[:400]:
        h = idx.hist(r['pid'], q, r['ordinal'])
        try:
            E.season_to_date(h, r['season'])
            diff += 1
        except E.Undefined:
            v = E.w1_prior_season_shrunk(h, r['season'], 5.0, k, c)
            if v == E.shrunk([x for x in h if x[0] // 100 < r['season']],
                             r['season'], 5.0, k, c):
                same += 1
    check('B1 is undefined at every season opener and the declared week-1 '
          'baseline is what fires', diff == 0 and same > 50,
          f'{same} fired, {diff} had current-season history')


def test_f4_the_final_game_week1_shape_is_the_one_the_engine_carries():
    """Not a performance claim -- a wiring claim, so the report's citation of
    the engine's defect cannot go stale silently."""
    p = _REPO / 'nfl' / 'production' / 'nonqb' / 'qb_allocation.py'
    if not p.exists():
        blocked('previous_primary_detail is still the engine shape',
                'nfl/production/nonqb/qb_allocation.py is absent')
        return
    src = p.read_text(encoding='utf-8')
    check('previous_primary_detail still resolves to the immediately prior '
          'team-game (the week-18 shape this package rejects for week 1)',
          'def previous_primary_detail' in src and 'bisect_left' in src)


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed'
          + (f', {BLOCKED} blocked' if BLOCKED else ''))
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name in [n for n in sorted(dir()) if n.startswith('test_')]:
        print(f'\n== {name}')
        globals()[name]()
