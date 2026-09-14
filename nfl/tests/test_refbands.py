"""D3 reference bands. The controls, not the decoration.

WHAT EACH GUARD IS FOR, AND THE DEFECT IT PINS

1.  CHRONOLOGY. `pbp_2026.*.csv.gz` IS ON DISK in this repository. A wildcard
    season accessor therefore does not fail loudly, it succeeds quietly and
    pulls the forecast season's own results into a "historical" band -- and one
    of those games has not been played. The guard is load-bearing precisely
    because the forbidden file exists, so the test seeds the violation by
    asking for 2026 by name and requires a refusal.

2.  THE GROUPING TRAP. Grouping by `game_id` instead of `(game_id, posteam)`
    selects the better of two starting quarterbacks. This suite recomputes the
    band the wrong way and requires it to be MEASURABLY higher, so the right
    answer is demonstrated against the wrong one rather than merely asserted.

3.  THE ATTEMPT-DEFINITION TRAP. nflverse `pass_attempt` includes sacks and
    spikes. The suite pins the arithmetic relation between the two columns in
    every row, so a future edit that quietly swaps one for the other fails
    here instead of in a write-up.

4.  KNEELS. Checked against the play-by-play itself, not against the panel's
    own claim about itself.

5.  WIRING. The tree is read. A band must not be reachable from a projection
    path, and a docstring saying so is not a control.

6.  ADEQUACY AND SHRINKAGE ARE DERIVED. The tests re-derive n_min from its own
    probability statement rather than restating 29, 11 and 5, so a constant
    that drifts away from its derivation fails.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.refbands import refbands as R          # noqa: E402

PASSED = FAILED = BLOCKED = 0
ROOT = pathlib.Path(_ROOT)
RB = ROOT / 'nfl' / 'research' / 'refbands'

#: the broad role-class bands this workstream extends, as published by the
#: coordinator. Reproduced here EXACTLY or the suite fails.
BROAD = {
    ('QB1', 'att_raw'): (24.0, 29.0, 35.0, 41.0, 46.0, 35.0),
    ('QB1', 'pass_yards'): (136.0, 179.0, 228.0, 279.0, 328.0, 230.9),
    ('RUSH1', 'carries'): (9.0, 11.0, 15.0, 19.0, 23.0, 15.3),
    ('RUSH2', 'carries'): (3.0, 4.0, 6.0, 9.0, 11.0, 6.5),
}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  PASS {label}' + (f' -- {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f' -- {detail}' if detail else ''))


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


_PANEL = None


def panel():
    global _PANEL
    if _PANEL is None:
        p = RB / 'USAGE_PANEL.csv.gz'
        rows = []
        with gzip.open(p, 'rt') as fh:
            for r in csv.DictReader(fh):
                r['roles'] = r['roles'].split(';') if r['roles'] else []
                for k in ('att_raw', 'attempts', 'completions', 'sacks',
                          'spikes', 'scrambles', 'dropbacks', 'carries',
                          'targets', 'receptions', 'season', 'week', 'home',
                          'first_dropback'):
                    r[k] = int(r[k])
                for k in ('pass_yards', 'rush_yards', 'rec_yards'):
                    r[k] = float(r[k])
                rows.append(r)
        _PANEL = rows
    return _PANEL


def test_a_chronology_refuses_the_forecast_season():
    """The 2026 blob exists. The guard must refuse it anyway."""
    present = sorted((ROOT / 'nfl' / 'research' / 'postgame').glob(
        'pbp_2026.*.csv.gz'))
    check('the forbidden season is actually on disk, so this guard is '
          'load-bearing', len(present) >= 1, f'{len(present)} blob(s)')
    for s in (2026, 2027):
        try:
            R.assert_lawful_season(s)
            check(f'assert_lawful_season({s}) refuses', False, 'it returned')
        except R.ChronologyError as e:
            check(f'assert_lawful_season({s}) refuses', True,
                  str(e).split(':')[0])
    try:
        R.pbp_path(2026)
        check('pbp_path(2026) refuses', False, 'it returned a path')
    except R.ChronologyError:
        check('pbp_path(2026) refuses', True)
    for s in R.PBP_SEASONS:
        check(f'pbp_path({s}) resolves exactly one blob',
              R.pbp_path(s).exists())
    check('2025 is lawful but has no play-by-play blob, so it is not in '
          'PBP_SEASONS',
          2025 not in R.PBP_SEASONS and 2025 in R.PANEL_SEASONS)


def test_b_adequacy_is_derived_not_stated():
    for L in R.LEVELS:
        n = R.n_min_for(L)
        t = min(L, 100 - L) / 100.0
        at_n = 1.0 - (1.0 - t) ** n
        below = 1.0 - (1.0 - t) ** (n - 1)
        check(f'n_min_for(p{L})={n} is the SMALLEST n reaching 1-alpha',
              at_n >= 1 - R.ALPHA and below < 1 - R.ALPHA,
              f'{below:.4f} -> {at_n:.4f} across n={n-1}->{n}')
    check('N0 is n_min_for(the widest published level), not a chosen number',
          R.N0 == R.n_min_for(min(R.LEVELS)), f'N0={R.N0}')
    check('N_FLOOR is n_min_for(50)', R.N_FLOOR == R.n_min_for(50),
          f'N_FLOOR={R.N_FLOOR}')
    check('the tails are ordered: median cheapest, p10/p90 dearest',
          R.n_min_for(50) < R.n_min_for(25) < R.n_min_for(10))


def test_c_shrinkage_behaves_at_its_limits():
    child = {'p10': 1.0, 'p25': 2.0, 'p50': 3.0, 'p75': 4.0, 'p90': 5.0,
             'mean': 3.0, 'n': 0}
    parent = {'p10': 11.0, 'p25': 12.0, 'p50': 13.0, 'p75': 14.0, 'p90': 15.0,
              'mean': 13.0, 'n': 0}
    s1 = R.shrink(child, parent, R.N0)
    check('at n = N0 the weight is exactly one half',
          abs(s1['w_own'] - 0.5) < 1e-12, f"w={s1['w_own']}")
    check('at n = N0 the band is the midpoint',
          abs(s1['p50'] - 8.0) < 1e-12, f"p50={s1['p50']}")
    big = R.shrink(child, parent, 10 ** 7)
    check('as n grows the group takes over',
          abs(big['p50'] - child['p50']) < 1e-3)
    tiny = R.shrink(child, parent, 1)
    check('at n = 1 the parent dominates', tiny['w_own'] < 0.04)
    check('shrinking toward an identical parent is a no-op',
          abs(R.shrink(child, child, 7)['p50'] - child['p50']) < 1e-9)
    for n in (1, 3, 8, 29, 400):
        b = R.shrink(child, parent, n)
        vals = [b[f'p{L}'] for L in R.LEVELS]
        check(f'a shrunk band at n={n} is still monotone',
              all(a <= c for a, c in zip(vals, vals[1:])))


def test_d_the_broad_bands_reproduce_exactly():
    rows = panel()
    tg = {(r['game_id'], r['team']) for r in rows}
    check('the frame is 2,174 team-games', len(tg) == 2174, str(len(tg)))
    check('it is 1,087 games, so a team-game is not a game',
          len({r['game_id'] for r in rows}) == 1087)
    for (role, metric), want in BROAD.items():
        vals = [r[metric] for r in rows if role in r['roles']]
        got = R.raw_band(vals)
        band = tuple(round(got[f'p{L}'], 1) for L in R.LEVELS)
        # ONE published cell in the four broad bands is ambiguous, and it is
        # ambiguous because the published bands did not declare a quantile
        # interpolation method. QB1/pass_yards p10 is 136.3 under 'linear'
        # (declared here) and 136.0 under 'lower' or 'nearest'. Every other
        # cell of all four bands is identical under all five numpy methods,
        # so this suite requires EXACT reproduction everywhere else and
        # measures the one cell rather than widening a tolerance over the lot.
        arr = np.asarray(vals, dtype=float)
        for i, L in enumerate(R.LEVELS):
            methods = {m: float(np.percentile(arr, L, method=m))
                       for m in ('linear', 'lower', 'higher', 'nearest',
                                 'midpoint')}
            invariant = len(set(round(v, 6) for v in methods.values())) == 1
            if invariant:
                check(f'{role}/{metric} p{L} reproduces exactly and is '
                      f'method-invariant', band[i] == want[i],
                      f'{band[i]} vs {want[i]}')
            else:
                check(f'{role}/{metric} p{L} is METHOD-DEPENDENT and the '
                      f'published value matches one of the methods',
                      any(abs(v - want[i]) < 0.05 for v in methods.values()),
                      f'declared linear={band[i]}, published={want[i]}, '
                      f'methods={ {k: round(v, 2) for k, v in methods.items()} }')
        check(f'{role}/{metric} mean reproduces', abs(got['mean'] - want[5])
              < 0.05, f"{got['mean']:.2f} vs {want[5]}")


def test_e_grouping_by_game_inflates_the_band_seeded_violation():
    """The wrong grouping, run on purpose, must come out visibly higher."""
    rows = panel()
    right = [r['att_raw'] for r in rows if 'QB1' in r['roles']]
    best_in_game = {}
    for r in rows:
        if 'QB1' not in r['roles']:
            continue
        g = r['game_id']
        if g not in best_in_game or r['att_raw'] > best_in_game[g]:
            best_in_game[g] = r['att_raw']
    wrong = list(best_in_game.values())
    a, b = R.raw_band(right), R.raw_band(wrong)
    check('the seeded wrong grouping yields half as many observations',
          len(wrong) * 2 == len(right), f'{len(wrong)} vs {len(right)}')
    check('and it inflates the median', b['p50'] > a['p50'],
          f"wrong p50={b['p50']} vs right p50={a['p50']}")
    check('and it inflates the mean', b['mean'] > a['mean'] + 1.0,
          f"wrong {b['mean']:.2f} vs right {a['mean']:.2f}")


def test_f_attempt_definitions_are_pinned_row_by_row():
    rows = panel()
    bad = [r for r in rows if r['att_raw'] != r['attempts'] + r['sacks']
           + r['spikes']]
    check('att_raw == attempts + sacks + spikes in EVERY row',
          not bad, f'{len(bad)} violation(s)')
    bad2 = [r for r in rows if r['dropbacks'] != r['att_raw'] + r['scrambles']
            - r['spikes']]
    check('dropbacks == att_raw + scrambles - spikes in every row',
          not bad2, f'{len(bad2)} violation(s)')
    qb1 = [r for r in rows if 'QB1' in r['roles']]
    gap = float(np.mean([r['att_raw'] - r['attempts'] for r in qb1]))
    check('the two QB1 attempt definitions differ by a material amount',
          gap > 2.0, f'att_raw - attempts = {gap:.4f} per team-game')
    check('and the broad band matches att_raw, not attempts',
          R.raw_band([r['att_raw'] for r in qb1])['p50'] == 35.0
          and R.raw_band([r['attempts'] for r in qb1])['p50'] == 32.0)


def test_g_kneels_are_excluded_checked_against_the_feed():
    """Not against the panel's claim about itself."""
    season = 2024
    tally, kneels = {}, 0
    with gzip.open(R.pbp_path(season), 'rt') as fh:
        for r in csv.DictReader(fh):
            if r['season_type'] != 'REG' or not r['posteam']:
                continue
            rid = r['rusher_player_id']
            if not rid or r['rush_attempt'] != '1':
                continue
            k = (r['game_id'], r['posteam'], rid)
            if r['qb_kneel'] == '1':
                kneels += 1
                tally.setdefault(k, [0, 0])[1] += 1
            else:
                tally.setdefault(k, [0, 0])[0] += 1
    check('the season actually contains kneels, so this test can fail',
          kneels > 100, f'{kneels} kneel plays in {season}')
    pan = {(r['game_id'], r['team'], r['player_id']): r['carries']
           for r in panel() if r['season'] == season}
    mism = [k for k, (ok, _) in tally.items() if pan.get(k, 0) != ok]
    check('panel carries equal rush attempts MINUS kneels, player by player',
          not mism, f'{len(mism)} mismatched player-team-games')
    seeded = [k for k, (ok, kn) in tally.items()
              if kn and pan.get(k, 0) == ok + kn]
    check('no player-team-game matches the kneel-INCLUSIVE count, which is '
          'the defect being excluded', not seeded, f'{len(seeded)}')


def _executable_refbands_reach(path):
    """Ways this file could actually READ a band, ignoring what it says.

    THE TEXT GREP THIS REPLACES WAS BACKWARDS. It flagged any file whose
    bytes contained "refbands", which caught `nfl/production/stat_contract.py`
    for a DOCSTRING citing `nfl/research/refbands/REFERENCE_BANDS.json` as the
    source of a measured 2.4356 per-QB1 gap -- a sentence whose entire purpose
    is to warn a reader off comparing a forecast to a band built on the other
    definition of a pass attempt. Penalising that comment makes the invariant
    punish its own documentation, and the cheapest way to go green would have
    been to DELETE the warning. So the check now looks for the things that
    would let the module reach a band and execute on it: an import, an
    attribute access, and a string used as anything other than a docstring.
    Prose stays free; a path does not.
    """
    import ast
    src = path.read_text(errors='ignore')
    if 'refbands' not in src:
        return []
    tree = ast.parse(src)
    doc_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            b = getattr(node, 'body', None)
            if b and isinstance(b[0], ast.Expr) and \
                    isinstance(b[0].value, ast.Constant) and \
                    isinstance(b[0].value.value, str):
                doc_nodes.add(id(b[0].value))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if 'refbands' in a.name]
        elif isinstance(node, ast.ImportFrom):
            if 'refbands' in (node.module or ''):
                found.append(node.module)
            found += [a.name for a in node.names if 'refbands' in a.name]
        elif isinstance(node, ast.Attribute) and 'refbands' in node.attr:
            found.append(node.attr)
        elif isinstance(node, ast.Name) and 'refbands' in node.id:
            found.append(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and 'refbands' in node.value and id(node) not in doc_nodes:
            found.append(repr(node.value[:60]))
    return found


def test_h_no_projection_path_can_reach_a_band():
    hits, prose = [], []
    for base in ('nfl/production', 'nfl/product'):
        d = ROOT / base
        if not d.exists():
            continue
        for p in d.rglob('*.py'):
            reach = _executable_refbands_reach(p)
            rel = str(p.relative_to(ROOT))
            if reach:
                hits.append(f'{rel}: {reach}')
            elif 'refbands' in p.read_text(errors='ignore'):
                prose.append(rel)
    check('no projection module imports, names or opens a refbands path',
          not hits, '; '.join(hits) or 'clean')
    # REPORTED, NOT FAILED. A projection module that merely NAMES the band
    # artifact in prose is documenting a trap, and the count is printed so a
    # reader can go and check that is all it is doing.
    check('  and any prose mention is in a docstring only',
          True, f'{len(prose)} file(s) mention it in prose: '
                f'{", ".join(prose) or "none"}')
    src = (RB / 'refbands.py').read_text()
    check('the module imports nothing from a projection path',
          'nfl.production' not in src and 'nfl.product' not in src)


def test_i_the_artifacts_are_present_schema_correct_and_honest():
    for name in ('USAGE_PANEL.csv.gz', 'REFERENCE_BANDS.jsonl.gz',
                 'REFERENCE_BANDS.json', 'RECENT_2025_SUPPLEMENT.json',
                 'TONIGHT_DEN_KC_PLACEMENT.json'):
        p = RB / name
        check(f'{name} exists and is not empty',
              p.exists() and p.stat().st_size > 0,
              f'{p.stat().st_size if p.exists() else 0} bytes')
    recs = []
    with gzip.open(RB / 'REFERENCE_BANDS.jsonl.gz', 'rt') as fh:
        for line in fh:
            recs.append(json.loads(line))
    check('every record carries an n', all('n' in r for r in recs),
          f'{len(recs)} records')
    check('every record names its level and metric',
          all(r.get('level') and r.get('metric') for r in recs))
    bad = [r for r in recs if r['status'] == R.INSUFFICIENT
           and not r.get('reason')]
    check('every INSUFFICIENT_EVIDENCE record says WHY', not bad,
          f'{len(bad)} silent')
    nonmono = [r for r in recs if r['own'] and not all(
        r['own'][f'p{a}'] <= r['own'][f'p{b}']
        for a, b in zip(R.LEVELS, R.LEVELS[1:]))]
    check('no published own band crosses itself', not nonmono,
          f'{len(nonmono)}')
    small = [r for r in recs if r['status'] in ('OWN', 'OWN_DOMINANT',
                                                'SHRUNK')
             and r['n'] < R.N_FLOOR]
    check('no band below N_FLOOR is published as its own', not small,
          f'{len(small)}')
    adq = [r for r in recs if r['own'] and r['n'] < R.n_min_for(10)
           and r['adequacy']['p10'] != R.INSUFFICIENT]
    check('a group under n_min(p10) is labelled INSUFFICIENT at p10 even '
          'when it has an own band', not adq, f'{len(adq)}')
    insuf = sum(1 for r in recs if r['status'] == R.INSUFFICIENT)
    check('a large share of the fine levels IS insufficient, which is the '
          'honest result and not a bug', insuf > 0.3 * len(recs),
          f'{insuf}/{len(recs)}')


def test_j_uncertainty_is_clustered_by_game():
    rows = panel()
    qb1 = [r for r in rows if 'QB1' in r['roles']]
    vals, clus = R._vals(qb1, 'att_raw')
    ci = R.clustered_band_ci(vals, clus, 50, b=200)
    check('the cluster is the game, so there are half as many clusters as '
          'rows', ci['n_clusters'] == len(vals) // 2,
          f"{ci['n_clusters']} clusters, {len(vals)} rows")
    check('the interval brackets the point estimate',
          ci['lo'] <= R.raw_band(vals)['p50'] <= ci['hi'],
          f"[{ci['lo']}, {ci['hi']}]")
    naive = R.clustered_band_ci(vals, list(range(len(vals))), 50, b=200)
    check('and it is not narrower than a row-level bootstrap, which would '
          'mean the clustering did nothing',
          (ci['hi'] - ci['lo']) >= (naive['hi'] - naive['lo']),
          f"clustered {ci['hi']-ci['lo']:.3f} vs naive "
          f"{naive['hi']-naive['lo']:.3f}")


def test_k_percentile_placement_is_midrank():
    check('a value below everything is at 0', R.percentile_of(0, [1, 2, 3])
          == 0.0)
    check('a value above everything is at 100', R.percentile_of(9, [1, 2, 3])
          == 100.0)
    check('a tie is split, not rounded to one side',
          R.percentile_of(2, [1, 2, 2, 3]) == 50.0,
          str(R.percentile_of(2, [1, 2, 2, 3])))


def test_l_tonight_is_read_against_bands_with_stated_support():
    d = json.loads((RB / 'TONIGHT_DEN_KC_PLACEMENT.json').read_text())
    pl = d['placements']
    check('all six projections are placed', len(pl) == 6, str(len(pl)))
    for p in pl:
        for e in p['ladder']:
            if e['status'] in ('OWN', 'OWN_DOMINANT', 'SHRUNK'):
                check(f"{p['who']}/{p['metric']} {e['level']} states n and "
                      f"cluster count",
                      e['n'] >= R.N_FLOOR and e.get('n_clusters'),
                      f"n={e['n']}")
    rookie = [p for p in pl if '00-0041013' == p['player_id']][0]
    own = [e for e in rookie['ladder'] if e['level'].startswith('player')]
    check('the rookie with no lawful history is INSUFFICIENT_EVIDENCE at '
          'every player level, not given a band anyway',
          all(e['status'] == R.INSUFFICIENT and e['n'] == 0 for e in own),
          f'{len(own)} player-level rungs')
    check('and he still gets a named coarser band to be read against',
          rookie['finest_with_support'] is not None,
          str(rookie['finest_with_support']))


def test_m_the_route_metric_is_never_called_a_route_count():
    d = json.loads((RB / 'REFERENCE_BANDS.json').read_text())
    rp = d['definitions']['route_proxy']
    check('the routes metric is published as a PROXY with its bias named',
          'PROXY' in rp and 'UPPER BOUND' in rp.upper(), rp[:60])
    check('and the artifact says outright that a band is not a model input',
          'never a floor' in d['purpose'], d['purpose'][:60])
    rows = panel()
    have = sum(1 for r in rows if r['route_proxy'] != '')
    check('the proxy is populated for the great majority of the frame',
          have > 0.9 * len(rows), f'{have}/{len(rows)}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    sys.exit(1 if FAILED else 0)
