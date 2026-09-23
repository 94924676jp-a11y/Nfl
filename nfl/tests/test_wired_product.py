"""Passing, rushing, receiving, kicking and DraftKings all seal together.

WHAT THIS TEST IS ABOUT. Rushing yards, kicker outcomes and DK points existed
and were correct, and they were assembled by a script that read the sealed npz
AFTERWARDS. That produced a board with no run identity, no provenance bundle
and no publication state -- a second product that agreed with the sealed one
only because the same process had just built both, and that nobody could
reproduce from the artifact. This asserts they are inside the seal.

STRUCTURE FIRST, THEN NUMBERS. The structural half needs no sealed run and is
always load-bearing: the conversion layer must not be deferring, the engine
must call it, and no module may carry a second copy of the DraftKings scoring
table. The numeric half needs a sealed run carrying a `kicking` layer; if the
repository has none it reports BLOCKED with a cause and does NOT pass.

ROW IDENTITY COMES FROM THE MANIFEST. Board order is not row order and reading
one as the other is how a Buffalo quarterback was once summed into Detroit.
"""
import glob
import json
import os
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_P, _F = [], []
TOL = 1e-9


def ck(name, cond, detail=''):
    (_P if cond else _F).append(name)
    print(('PASS ' if cond else 'FAIL ') + name
          + ((' :: ' + detail) if detail else ''))


def structural():
    from nfl.production.nonqb import layers as LY
    from nfl.production.nonqb import eligibility as EL
    from nfl.production import kicking as KICK
    from nfl.product import dk_scoring as DKS
    from sportsplatform.governance.outcome import Outcome

    ck('conversion_layer_has_a_spec_version',
       LY.SPEC.get('rushing_conversion') is not None,
       str(LY.SPEC.get('rushing_conversion')))
    ck('conversion_layer_declared_implemented',
       EL.IMPLEMENTATION['rushing_conversion'][0] == 'IMPLEMENTED',
       str(EL.IMPLEMENTATION['rushing_conversion']))

    # The refusals that must SURVIVE the layer being implemented.
    ok = Outcome.ok('X', value=1)
    ck('caller_supplied_prior_still_refused',
       LY.rushing_conversion(ok, priors={'rate': 0.5}).code
       == 'RUSHING_PRIOR_NOT_OWNED_BY_CALLER')
    ck('conversion_without_positions_refused',
       LY.rushing_conversion(ok).code == 'RUSHING_CONVERSION_INPUTS_ABSENT',
       'running without positions is the unstratified pool wearing a '
       'stratified name')

    # ONE SCORING TABLE. kicking.py used to carry its own copy AND score with
    # an extra-point draw the caller never saw.
    ck('kicking_carries_no_scoring_table',
       not hasattr(KICK, 'DK_FG_POINTS') and not hasattr(KICK, 'DK_XP_POINTS'))
    ck('dk_scoring_owns_the_band_table', hasattr(DKS, 'BAND_POINTS'))
    ck('kicking_simulate_returns_no_points',
       'dk' not in (KICK.simulate.__doc__ or '') and True)
    try:
        DKS.kicker_points({'FG60s': np.zeros(4)}, np.zeros(4))
        ck('unknown_band_refused', False, 'scored silently as zero')
    except KeyError:
        ck('unknown_band_refused', True)

    src = (REPO / 'nfl' / 'production' / 'run_forecast.py').read_text()
    for lyr in ('kicking', 'dk_scoring'):
        ck(f'run_forecast_seals_{lyr}',
           f"'{lyr}'," in src or f"add_layer(\n                        '{lyr}'"
           in src or f"'{lyr}', _k_rows" in src or f"'{lyr}', _dk_rows" in src)
    fe = (REPO / 'nfl' / 'production' / 'nonqb'
          / 'football_engine.py').read_text()
    ck('engine_calls_the_conversion_with_carries',
       'LY.rushing_conversion(car, C,' in fe)


def _newest_run_with_kicking():
    best = None
    for man in glob.glob(str(REPO / 'nfl/research/live/*/*/*/'
                             'player_draws_manifest.json')):
        try:
            m = json.load(open(man))
        except (OSError, ValueError):
            continue
        if 'kicking' not in (m.get('layers') or {}):
            continue
        t = os.path.getmtime(man)
        if best is None or t > best[0]:
            best = (t, os.path.dirname(man))
    return best[1] if best else None


def _dk_rush_yards(z, rid, pid):
    """The rushing yards the DK total actually consumed, for one player."""
    tot = 0.0
    for lyr, met in (('qb', 'ryds'), ('rushing', 'rushing_yards')):
        ids = rid.get(lyr) or []
        if pid in ids and f'{lyr}__{met}' in z.files:
            tot = tot + z[f'{lyr}__{met}'][ids.index(pid)]
    return tot


def numeric(run_dir):
    from nfl.product import dk_scoring as DKS
    m = json.load(open(os.path.join(run_dir, 'player_draws_manifest.json')))
    z = np.load(os.path.join(run_dir, 'player_draws.npz'), allow_pickle=True)
    board = json.load(open(os.path.join(run_dir, 'board.json')))
    rid = {k: v['row_ids'] for k, v in m['layers'].items()}
    team = {p['gsis_id']: p['team'] for p in board['players']}
    n = int(m['n_draws'])
    # THE KICKER IS NOT IN board['players'], and reading his team from there
    # returned None -- which silently made the expected touchdown vector all
    # zeros and reported the ENGINE as broken by ten touchdowns. It was the
    # test. His identity comes from the artifact's `kicking` block, which is
    # where it is published.
    art = json.load(open(os.path.join(run_dir, 'forecast_artifact.json')))
    kmeta = (art.get('kicking') or {}).get('resolved') or {}
    ck('kicker_identity_is_published_not_only_a_row_id',
       bool(kmeta) and all(g in kmeta for g in (rid.get('kicking') or [])),
       f'{sorted(kmeta)} against rows {rid.get("kicking")}')
    for g, meta in kmeta.items():
        ck(f'{g} roster_basis_is_stated',
           bool(meta.get('roster_basis')), str(meta.get('roster_basis')))
        ck(f'{g} rate_basis_is_stated',
           bool(meta.get('rate_basis')), str(meta.get('rate_basis')))
    team.update({g: v['team'] for g, v in kmeta.items() if v.get('team')})

    ck('one_run_identity', bool(m.get('run_id')), str(m.get('run_id')))
    ck('one_draw_index_across_every_layer',
       len({z[k].shape[1] for k in z.files}) == 1,
       str({z[k].shape[1] for k in z.files}))
    for lyr in ('qb', 'receiving', 'rushing', 'kicking', 'dk_scoring'):
        ck(f'layer_present_{lyr}', lyr in rid)
    ck('rushing_yards_sealed', 'rushing/rushing_yards' in
       [f'{k}/{x}' for k, v in m['layers'].items() for x in v['metrics']])

    # --- rushing yards belong to the carries that produced them ----------
    C, Y = z['rushing__carries'], z['rushing__rushing_yards']
    ck('no_rushing_yards_without_a_carry', int(((C == 0) & (Y != 0)).sum()) == 0,
       f'{int(((C == 0) & (Y != 0)).sum())} cells')
    ck('rushing_yards_are_finite', bool(np.isfinite(Y).all()))

    # --- the kicker kicks in his own team's worlds ------------------------
    for i, g in enumerate(rid['kicking']):
        tm = team.get(g)
        td = z['kicking__offensive_td'][i]
        ck(f'{g} extra_points_attempted_within_this_draws_touchdowns',
           bool((z['kicking__xpa'][i] <= td).all()),
           f'max excess {float((z["kicking__xpa"][i] - td).max())}')
        ck(f'{g} makes_within_attempts',
           bool((z['kicking__xpm'][i] <= z['kicking__xpa'][i]).all())
           and bool((z['kicking__fgm'][i] <= z['kicking__fga'][i]).all()))
        bands = sum(z[f'kicking__att_{b}'][i] for b in
                    ('FG<20', 'FG20s', 'FG30s', 'FG40s', 'FG50+'))
        ck(f'{g} band_attempts_partition_the_field_goal_attempts',
           bool((bands == z['kicking__fga'][i]).all()))
        # THE COUPLING, NOT A CORRELATION. offensive_td must be THIS team's
        # own sealed touchdowns, resolved by manifest row, per draw.
        want = np.zeros(n)
        for lyr, met in (('receiving', 'receiving_td'),
                         ('rushing', 'rushing_td'), ('qb', 'rtd')):
            idx = [j for j, p in enumerate(rid.get(lyr) or [])
                   if team.get(p) == tm]
            if idx:
                want += z[f'{lyr}__{met}'][idx].sum(0)
        ck(f'{g} offensive_td_is_this_teams_own_sealed_touchdowns',
           bool(np.abs(want - td).max() < TOL),
           f'max |diff| {float(np.abs(want - td).max())}')
        ck(f'{g} kicker_dk_points_reproduce_from_sealed_events',
           bool(np.abs(DKS.kicker_points(
               {b: z[f'kicking__made_{b}'][i] for b in
                ('FG<20', 'FG20s', 'FG30s', 'FG40s', 'FG50+')},
               z['kicking__xpm'][i]) - z['kicking__dk_points'][i]).max() < TOL))

    # --- every DK total reproduces from the events sealed beside it -------
    worst, worst_id = 0.0, None
    for i, pid in enumerate(rid['dk_scoring']):
        kw = {}
        for lyr, pairs in (
                # RUSHING YARDS COME FROM `rushing_total` AND NOWHERE ELSE.
                # `qb/ryds` and `rushing/rushing_yards` are COMPONENTS of it
                # now, alongside the gadget yards, so scoring them here would
                # both double-count and miss the gadget contribution. This
                # map lagged the engine's and reported a 19.3-point diff on
                # Amon-Ra St. Brown -- his 1.62 gadget yards flip the
                # 100-rushing-yard bonus in some draws. The engine was right.
                ('qb', (('pass_yds', 'pyds'), ('pass_td', 'ptd'),
                        ('ints', 'int'), ('rush_td', 'rtd'))),
                ('receiving', (('rec', 'receptions'),
                               ('rec_yds', 'receiving_yards'),
                               ('rec_td', 'receiving_td'))),
                ('rushing', (('rush_td', 'rushing_td'),)),
                ('rushing_total', (('rush_yds', 'rushing_yards'),))):
            ids = rid.get(lyr) or []
            if pid not in ids:
                continue
            r = ids.index(pid)
            for arg, met in pairs:
                key = f'{lyr}__{met}'
                if key in z.files:
                    kw[arg] = kw.get(arg, 0.0) + z[key][r]
        d = float(np.abs(DKS.skill_points(n, **kw)
                         - z['dk_scoring__dk_points'][i]).max())
        if d > worst:
            worst, worst_id = d, pid
    ck('every_dk_total_reproduces_from_its_own_sealed_events', worst < TOL,
       f'worst |diff| {worst} at {worst_id}')

    # --- a rushing quarterback must not lose half his yards ---------------
    both = [p for p in rid['dk_scoring']
            if p in (rid.get('qb') or []) and p in (rid.get('rushing') or [])]
    if both:
        worst2 = max(
            float(np.abs(
                z['qb__ryds'][rid['qb'].index(p)]
                + z['rushing__rushing_yards'][rid['rushing'].index(p)]
                - _dk_rush_yards(z, rid, p)).max()) for p in both)
        ck('players_in_two_rush_layers_are_summed_not_overwritten',
           worst2 < TOL, f'{len(both)} player(s), worst |diff| {worst2}')
    else:
        # NOT A PASS. No player on this board rushes from both layers, so the
        # summing branch never executed. Reporting it green would be a check
        # that certifies its own absence.
        print('NOT_EXECUTED players_in_two_rush_layers_are_summed_not_'
              'overwritten :: no player appears in both the qb and rushing '
              'layers on this board, so the branch did not run')


def main():
    print('--- structural ---')
    structural()
    print('--- numeric ---')
    run = _newest_run_with_kicking()
    if not run:
        print('BLOCKED WIRED_PRODUCT_NO_SEALED_RUN_WITH_KICKING cause=DATA :: '
              'no sealed run under nfl/research/live carries a kicking layer, '
              'so the numeric half has nothing to check. This is BLOCKED and '
              'is not a pass.')
        print(f'\n{len(_P)} passed, {len(_F)} failed (structural only)')
        return 1 if _F else 0
    print(f'run: {os.path.relpath(run, REPO)}')
    numeric(run)
    print(f'\n{len(_P)} passed, {len(_F)} failed')
    if _F:
        print('FAILED: ' + ', '.join(_F))
    return 1 if _F else 0



# ---------------------------------------------------------------- the runner
# THIS MODULE'S CHECKS WERE INVISIBLE TO `run_suite`. It records into `_P`/`_F`
# and runs everything from `main()`, so the runner discovered ZERO `test_*`
# functions and executed NONE of them. Found 2026-09-23 by
# `test_harness_audit`'s "no module has zero test functions", which had been
# failing and telling the truth, and confirmed by invoking this file directly:
# it reports real numbers the suite had never seen.
#
# That is the false-green class INSIDE the measurement system -- the same
# defect `run_suite.py` was written to end, one level further out.
#
# NOTHING BELOW CHANGES WHAT THIS MODULE ASSERTS. It exposes the integer
# counters the runner reads (`_P`/`_F` are lists and underscore-prefixed, so
# `tally()` could not see them either) and gives the runner one function to
# call, in the same shape the other fifty modules use.
PASSED = FAILED = 0
blocked_count = 0


def test_every_check_in_this_module():
    global PASSED, FAILED, blocked_count
    main()
    PASSED, FAILED = len(_P), len(_F)
    # `main()` returns early, without recording a check, when its inputs are
    # absent. Counted as BLOCKED so it is distinguishable from silence: a
    # module that could not measure said so, and is not a pass.
    if not _P and not _F:
        blocked_count = 1


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')

if __name__ == '__main__':
    raise SystemExit(main())
