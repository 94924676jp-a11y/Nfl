"""QBSEM acceptance item 6: every cell feature is known before kickoff.

The cell is `starter_cell(rank_bucket, was_prev_primary, is_opener)`. Each
component is asserted against the clock, mechanically, not by inspection:

  rank              the depth chart, selected AS OF the forecast instant by
                    `qb_allocation` -- a chart retrieved after `written_at`
                    must never be the selected one
  was_prev_primary  the club's previous primary passer, from ordinals
                    STRICTLY EARLIER than this one
  is_opener         whether that previous ordinal belongs to an earlier
                    season -- a fact about two ordinals and nothing else

and the RATE attached to the cell:

  p_relief_given_not_starter  fitted on team-games with ordinal < the cut,
                              by the same `fit` that fits `p_start`

WHAT THIS CANNOT PROVE. It proves no FUTURE byte reaches the cell. It cannot
prove the cell is a good feature, and it cannot prove specification leakage is
absent: the frame these cells were chosen on is the frame every earlier QB
repair was selected on. That is declared EXPLORATORY in the pre-registration
and no test can launder it.
"""
from __future__ import annotations

import ast
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production.nonqb import qb_room_v2 as V2                  # noqa: E402

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


def test_A_the_rate_sees_nothing_at_or_after_the_cut():
    print('\nA. the cell rate is fitted STRICTLY BEFORE the evaluation ordinal')
    tg = V2.load_pbp(V2.HISTORICAL_SEASONS)
    ords = sorted({g['season'] * 100 + g['week'] for g in tg.values()})
    cut = ords[len(ords) // 2]
    fit_all = V2.fit_for_ordinal(ords[-1] + 1)
    fit_cut = V2.fit(_frame(tg), tg, cut)

    n_all = sum(fit_all['n_relief_given_not_starter'].values())
    n_cut = sum(fit_cut['n_relief_given_not_starter'].values())
    check(f'a cut at {cut} sees strictly fewer rows than the full window',
          0 < n_cut < n_all, f'{n_cut} vs {n_all}')
    check('  and the fit declares the cut it honoured',
          fit_cut['trained_on_ordinals_before'] == cut,
          str(fit_cut.get('trained_on_ordinals_before')))

    # THE BEHAVIOURAL FORM. Counting rows by hand from the frame and comparing
    # against the fit's own counters catches a `>=` written as a `>`, which
    # reading the line would not.
    want = {}
    for r in _frame(tg):
        if r['ord'] >= cut or r['is_starter']:
            continue
        c = V2.starter_cell(r['rank'], r['was_prev_primary'], r['is_opener'])
        want[c] = want.get(c, 0) + 1
    check('  every counted row is strictly earlier than the cut, cell by cell',
          {k: v for k, v in fit_cut['n_relief_given_not_starter'].items() if v}
          == {k: v for k, v in want.items() if v},
          'the fit counted a row the cut excludes, or missed one it includes')

    later = [r for r in _frame(tg) if r['ord'] >= cut]
    check(f'  {len(later)} row(s) at or after the cut exist and are excluded',
          bool(later) and n_cut < n_all,
          'nothing was withheld, so this test proved nothing')


_FRAME = None


def _frame(tg):
    global _FRAME
    if _FRAME is None:
        pp = V2.previous_primary_from_panel()
        weekly = [y for y in V2.HISTORICAL_SEASONS
                  if os.path.exists(V2.DC_WEEKLY % y)]
        dw = V2.load_depth_weekly(weekly) if weekly else {}
        depth = {}
        for k, g in tg.items():
            r = dw.get((g['season'], g['week'], g['team']))
            if r:
                depth[k] = r
        dates = {k: g['date'] for k, g in tg.items() if k not in depth}
        if dates:
            for k, v in V2.load_depth_daily_asof(dates).items():
                depth.setdefault(k, v)
        _FRAME = V2.build_frame(tg, depth, pp)
    return _FRAME


def test_B_the_cell_function_reads_only_its_three_arguments():
    print('\nB. `starter_cell` is a pure function of three pregame facts')
    src = open(V2.__file__).read()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == 'starter_cell')
    args = {a.arg for a in fn.args.args}
    check('its arguments are exactly the declared cell components',
          args == {'rank', 'was_prev', 'is_opener', 'use_opener'}, str(args))
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    free = names - args - {'rank_bucket', 'int', 'bool'}
    check('  it reads no module state, no clock and no file', not free,
          f'free names: {sorted(free)}')
    calls = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    check('  it calls nothing but rank_bucket, int and bool',
          calls <= {'rank_bucket', 'int', 'bool'}, str(sorted(calls)))


def test_C_the_previous_primary_is_strictly_earlier():
    print('\nC. `was_prev_primary` and `is_opener` come from an EARLIER ordinal')
    from nfl.production.nonqb import qb_allocation as QA
    det = QA.previous_primary_detail(2026, 2)
    cut = 2026 * 100 + 2
    bad = [(t, d) for t, d in det.items()
           if d.get('ordinal') is not None and d['ordinal'] >= cut]
    check('no club`s previous primary is drawn from this ordinal or later',
          not bad, str(bad[:3]))
    check('  and the opener flag is derived from that ordinal, not from week',
          all(d.get('is_season_opener') is None
              or d['is_season_opener'] == ((d['ordinal'] // 100) != 2026)
              for d in det.values() if d.get('ordinal') is not None),
          'the flag disagrees with the ordinals it claims to summarise')
    # THE LIVE CONSEQUENCE, RECORDED NOT REPAIRED. With no 2026 play-by-play
    # in the panel, every club's previous primary is a 2025 week-18
    # quarterback, so a week-2 game is classed as a season opener. That is
    # QB3_WEEK1_SEASON_BOUNDARY, already declared on the artifact. It is a
    # STALENESS defect, not a leakage defect -- the signal is too old, never
    # too new -- and it is what puts both DET-BUF starters in a cell with no
    # non-starting rows.
    ords = {d.get('ordinal') for d in det.values() if d.get('ordinal')}
    print(f'       previous-primary ordinals in force for 2026 week 2: '
          f'{sorted(ords)}')
    check('  every one of them is in the PAST, which is what leakage means',
          all(o < cut for o in ords), str(sorted(ords)))


def test_D_no_outcome_of_the_forecast_game_enters_the_cell():
    print('\nD. nothing downstream of kickoff is in the estimator')
    src = open(V2.__file__).read()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == 'fit')
    # The fit reads the frame and team_games; both are HISTORICAL by
    # construction and the cut is applied to both. What must not appear is a
    # read of anything priced, quoted or scored.
    src_fn = ast.get_source_segment(src, fn) or ''
    for word in ('odds', 'price', 'book', 'market', 'vig', 'line_',
                 'draftkings', 'dk_', 'hardrock', 'fanduel', 'projection'):
        check(f'  `fit` contains no reference to {word!r}',
              word not in src_fn.lower(), 'a market term reached the fit')
    check('  the cut is applied to the frame', "r['ord'] >= cut" in src_fn)
    check('  and to the team-games the pools are drawn from',
          'if o >= cut' in src_fn)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED.

    `run_suite` reads PASSED/FAILED and folds them into the aggregate, but a
    module with no re-raising tripwire is classified PASS however many of its
    checks failed -- the count moves and the module does not. Fifty modules in
    this suite end with exactly this, and without it a tripwire cannot trip.
    """
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_rate_sees_nothing_at_or_after_the_cut,
               test_B_the_cell_function_reads_only_its_three_arguments,
               test_C_the_previous_primary_is_strictly_earlier,
               test_D_no_outcome_of_the_forecast_game_enters_the_cell):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    raise SystemExit(1 if FAILED else 0)
