"""An entered lineup is accounted for whole, or refused whole.

WHAT THIS MODULE ASSERTS
========================
1. A SLOT THE ENGINE DOES NOT MODEL REFUSES THE WHOLE LINEUP. Not a partial
   total, not a warning beside a number. Against the real 2026-09-24 entry,
   Pierre Strong resolves to nothing: DEV roster status, absent from every
   draw layer, absent from all 958 rows of the DK file we held, while the live
   contest priced him. Summing the other five and printing the result is how a
   missing player becomes invisible.
2. AN AMBIGUOUS ABBREVIATION IS REPORTED, NEVER GUESSED. DK renders
   "B. Robinson" and Atlanta rosters two, $11,100 apart at captain. Every
   candidate comes back with its salary so a human or a contest export
   resolves it. Inferring from price would be a fuzzy match wearing
   arithmetic.
3. ACCOUNTABLE IS NOT AN ENDORSEMENT. The passing verdict says in its own
   detail that it claims nothing about whether the lineup is good, because
   ranking lineups needs covariance the draw artifact declares it lacks.
4. THE STRUCTURAL RULES HOLD: six slots, exactly one captain, captain salary
   drawn from the captain column, and the cap enforced.
5. A DECLARED-UNAVAILABLE PLAYER IS SURFACED rather than silently carried.
"""
import csv
import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.dfs.lineup_integrity import (  # noqa: E402
    DEFAULT_SALARY_CAP,
    LineupRefusal,
    candidates_for,
    check,
)

PASSED = FAILED = BLOCKED = 0

SLICE = pathlib.Path(_ROOT) / 'nfl' / 'dfs' / 'vintage' / \
    'dk_showdown_2026_03_ATL_GB.slice.csv'
RUN = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'unsealed' / \
    '2026_03_ATL_GB' / '2fc4e9599f0889f1'


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def _pool():
    pool = {}
    for r in csv.DictReader(open(SLICE)):
        e = pool.setdefault(r['Player'], {'team': r['Team']})
        e['CPT' if r['Pos'] == 'CPTN' else 'FLEX'] = int(r['Salary'])
    return pool


def _toy():
    return {'Alpha One': {'team': 'GB', 'CPT': 15000, 'FLEX': 10000},
            'Beta Two': {'team': 'GB', 'CPT': 9000, 'FLEX': 6000},
            'Gamma Three': {'team': 'ATL', 'CPT': 7500, 'FLEX': 5000},
            'Delta Four': {'team': 'ATL', 'CPT': 6000, 'FLEX': 4000},
            'Epsilon Five': {'team': 'GB', 'CPT': 4500, 'FLEX': 3000},
            'Zeta Six': {'team': 'ATL', 'CPT': 3000, 'FLEX': 2000}}


def _toy_lineup():
    names = list(_toy())
    return [{'slot': 'CPT', 'name': names[0]}] + \
           [{'slot': 'FLEX', 'name': n} for n in names[1:]]


def test_a_clean_lineup_is_accountable_but_not_endorsed():
    pool = _toy()
    ids = {n: f'00-{i:07d}' for i, n in enumerate(pool)}
    v = check(_toy_lineup(), pool=pool, crosswalk=ids,
              modelled_ids=set(ids.values()))
    chk('it is accountable', v['state'] == 'ACCOUNTABLE', v['state'])
    chk('captain salary comes from the captain column',
        v['salary_used'] == 15000 + 6000 + 5000 + 4000 + 3000 + 2000,
        str(v['salary_used']))
    chk('salary remaining is reported',
        v['salary_remaining'] == DEFAULT_SALARY_CAP - v['salary_used'])
    chk('and the verdict explicitly disclaims any quality judgement',
        'NOTHING about whether it is a good lineup' in v['detail'])


def test_an_unmodelled_player_refuses_the_whole_lineup():
    pool = dict(_toy())
    pool['Ghost Player'] = {'team': 'GB', 'CPT': 1500, 'FLEX': 1000}
    ids = {n: f'00-{i:07d}' for i, n in enumerate(_toy())}
    lu = _toy_lineup()
    lu[-1] = {'slot': 'FLEX', 'name': 'Ghost Player'}
    v = check(lu, pool=pool, crosswalk=ids, modelled_ids=set(ids.values()))
    chk('the lineup is REFUSED', v['state'] == 'REFUSED', v['state'])
    chk('with the named code', v['code'] == 'LINEUP_NOT_ACCOUNTABLE')
    chk('naming the unmodelled player', v['unmodelled'] == ['Ghost Player'])
    chk('and refusing to report a partial total as a total',
        'partial total reported as a total' in v['detail'])


def test_an_ambiguous_abbreviation_is_reported_never_guessed():
    pool = {'Bijan Robinson': {'team': 'ATL', 'CPT': 17700, 'FLEX': 11800},
            'Brian Robinson': {'team': 'ATL', 'CPT': 6600, 'FLEX': 4400}}
    cands = candidates_for('B. Robinson', list(pool))
    chk('both Robinsons are candidates',
        cands == ['Bijan Robinson', 'Brian Robinson'], str(cands))
    chk('a full name still resolves to exactly one',
        candidates_for('Bijan Robinson', list(pool)) == ['Bijan Robinson'])
    chk('a different surname matches neither',
        candidates_for('B. Watson', list(pool)) == [])

    full = dict(_toy())
    full.update(pool)
    lu = _toy_lineup()
    lu[0] = {'slot': 'CPT', 'name': 'B. Robinson'}
    v = check(lu, pool=full, crosswalk={}, modelled_ids=None)
    chk('the lineup is refused on ambiguity', v['state'] == 'REFUSED')
    amb = v['ambiguous'][0]
    chk('both candidates come back with their captain salaries',
        {c['name']: c['salary'] for c in amb['candidates']}
        == {'Bijan Robinson': 17700, 'Brian Robinson': 6600},
        str(amb['candidates']))


def test_structural_rules():
    pool = _toy()
    try:
        check([], pool=pool)
        chk('an empty lineup raises', False, 'it was accepted')
    except LineupRefusal as e:
        chk('an empty lineup raises', e.code == 'LINEUP_EMPTY')
    try:
        check(_toy_lineup()[:5], pool=pool)
        chk('five slots raises', False, 'it was accepted')
    except LineupRefusal as e:
        chk('five slots raises', e.code == 'LINEUP_WRONG_SIZE')
    two_cpt = _toy_lineup()
    two_cpt[1]['slot'] = 'CPT'
    try:
        check(two_cpt, pool=pool)
        chk('two captains raises', False, 'it was accepted')
    except LineupRefusal as e:
        chk('two captains raises', e.code == 'LINEUP_CAPTAIN_COUNT')

    rich = {n: {'team': 'GB', 'CPT': 20000, 'FLEX': 15000} for n in _toy()}
    v = check(_toy_lineup(), pool=rich, crosswalk={}, modelled_ids=None)
    chk('an over-cap lineup is refused', v['code'] == 'LINEUP_OVER_CAP',
        v['code'])


def test_a_declared_unavailable_player_is_surfaced():
    pool = _toy()
    ids = {n: f'00-{i:07d}' for i, n in enumerate(pool)}
    v = check(_toy_lineup(), pool=pool, crosswalk=ids,
              modelled_ids=set(ids.values()),
              availability={ids['Beta Two']: 'OUT'})
    chk('the OUT player is named',
        v['declared_unavailable'] == [{'name': 'Beta Two',
                                       'availability': 'OUT'}],
        str(v['declared_unavailable']))


def test_the_real_entered_lineup_is_refused_for_both_reasons():
    if not SLICE.exists() or not RUN.is_dir():
        return blocked('live entry', 'DK slice or run artifacts absent')
    import numpy as np
    pool = _pool()
    cw = json.loads((pathlib.Path(_ROOT) / 'nfl' / 'dfs' / 'vintage' /
                     'dk_showdown_2026_03_ATL_GB.crosswalk.json').read_text())
    xw = {e['dk_name']: e['gsis_id'] for e in cw['entries'] if e.get('gsis_id')}
    m = json.loads((RUN / 'player_draws_manifest.json').read_text())
    modelled = set(m['layers']['dk_scoring']['row_ids'])

    lineup = [{'slot': 'CPT', 'name': 'B. Robinson'},
              {'slot': 'FLEX', 'name': 'C. Watson'},
              {'slot': 'FLEX', 'name': 'M. Penix Jr.'},
              {'slot': 'FLEX', 'name': 'D. London'},
              {'slot': 'FLEX', 'name': 'Z. Branch'},
              {'slot': 'FLEX', 'name': 'P. Strong Jr.'}]
    v = check(lineup, pool=pool, crosswalk=xw, modelled_ids=modelled)
    chk('the live entry is REFUSED', v['state'] == 'REFUSED', v['state'])
    chk('Pierre Strong is not in the pool at all',
        any(s.get('resolution') == 'NOT_IN_POOL'
            and s['entered'] == 'P. Strong Jr.' for s in v['slots']))
    chk('the captain slot is ambiguous',
        v['n_ambiguous'] == 1
        and v['ambiguous'][0]['entered'] == 'B. Robinson')
    chk('the other four slots resolved cleanly',
        sum(1 for s in v['slots'] if s.get('resolution') == 'RESOLVED') == 4)
    chk('and each of those is modelled by the engine',
        all(s.get('modelled') for s in v['slots']
            if s.get('resolution') == 'RESOLVED'))
    print('       refused for: ' + v['detail'][:96])


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
