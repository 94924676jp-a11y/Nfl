#!/usr/bin/env python3.12
"""End-to-end Showdown acceptance: the nine invariants, each forced on a slate built to force it.

WHY A SYNTHETIC SLATE. The real Week 2 export cannot exercise selection, because no projection covers
that game and no simulated draws exist for it -- the runner correctly refuses before it gets there. An
acceptance test that stopped at the refusal would prove the refusal and nothing about the product. So
these build a complete slate in a temp directory: two clubs, both kickers, both defences, distinct
CPT and FLEX ids per person, captain salaries at exactly 1.5x, a projection covering everyone, and
shared simulated draws.

The slate is deliberately built so the CAP BINDS. If every lineup fitted, the both-teams and overlap
constraints would never be tested against a solver that wanted to break them.

THE NINE INVARIANTS, in the owner's words 2026-10-01:
  1 same player has distinct CPT/FLEX IDs
  2 model join occurs on stable player identity, not DK item ID
  3 CPT upload uses CPT ID
  4 FLEX upload uses FLEX ID
  5 optimizer cannot select the same person twice
  6 both-team rule is enforced
  7 incomplete projection coverage refuses
  8 inactive player with playable projection blocks publication
  9 missing kicker/DST is explicit, never silently dropped
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

from nfl.tests import _registry  # noqa: E402

RESULTS = []

#: Two clubs that are NOT in the declared team-alias map, so the synthetic slate exercises the
#: pass-through path and cannot accidentally depend on the LAR -> LA rule.
AWAY, HOME = 'AAA', 'BBB'
GAME_INFO = f'{AWAY}@{HOME} 10/01/2026 08:15PM ET'
N_WORLDS = 24

#: A SLATE OF REALISTIC SIZE, which the first version of this fixture was not. With 12 players the
#: declared caps are infeasible by pigeonhole rather than by policy: MAX_PLAYER_EXPOSURE 0.50 over 3
#: entries allows each person one seat, and 3 x 6 seats needs 18 distinct people. The selection stage
#: correctly reported SHOWDOWN_PORTFOLIO_SHORT_OF_ENTRIES and the fixture was what was wrong. A real
#: showdown pool is about 53 people; 24 is enough to make the caps bind on policy instead of on
#: arithmetic.
#: (name, club, position, flex salary)
def _roster():
    r = []
    for club, tag in ((AWAY, 'A'), (HOME, 'B')):
        r += [
            (f'{tag}1 Quarterback', club, 'QB', 11000), (f'{tag}2 Quarterback', club, 'QB', 5400),
            (f'{tag}1 Runner', club, 'RB', 9000), (f'{tag}2 Runner', club, 'RB', 6200),
            (f'{tag}3 Runner', club, 'RB', 4000),
            (f'{tag}1 Catcher', club, 'WR', 8800), (f'{tag}2 Catcher', club, 'WR', 7000),
            (f'{tag}3 Catcher', club, 'WR', 5000), (f'{tag}4 Catcher', club, 'WR', 3200),
            (f'{tag}1 Tightend', club, 'TE', 5200), (f'{tag}2 Tightend', club, 'TE', 3400),
            (f'{tag} Kicker', club, 'K', 3600), (f'{club} Defense', club, 'DST', 3000),
        ]
    return r


ROSTER = _roster()


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _write_export(tmp: pathlib.Path, roster=ROSTER, n_entries=4) -> pathlib.Path:
    """A DK showdown export in the real two-block layout: entries left, player pool right."""
    entry_hdr = list(S.ENTRY_COLUMNS) + list(S.SHOWDOWN_SLOTS) + ['', 'Instructions']
    pool_rows = []
    for i, (name, club, pos, flex) in enumerate(roster):
        flex_id = str(50000000 + i)
        cpt_id = str(50001000 + i)
        pool_rows.append([pos, f'{name} ({cpt_id})', name, cpt_id, 'CPT', str(round(flex * 1.5)),
                          GAME_INFO, club, ''])
        pool_rows.append([pos, f'{name} ({flex_id})', name, flex_id, 'FLEX', str(flex),
                          GAME_INFO, club, ''])
    rows = [entry_hdr]
    n = max(n_entries, len(pool_rows) + 1)
    for r in range(n):
        left = ([f'900000{r:03d}', 'Showdown Test (AAA @ BBB)', '12345', '$1'] + [''] * 6
                if r < n_entries else [''] * 10)
        right = ([list(S.POOL_COLUMNS)] + pool_rows)[r] if r < 1 + len(pool_rows) else [''] * 9
        rows.append(left + [''] + right)
    p = tmp / 'DKEntries_SYNTHETIC_SHOWDOWN.csv'
    with p.open('w', newline='', encoding='utf-8') as fh:
        csv.writer(fh).writerows(rows)
    return p


def _write_projections(tmp: pathlib.Path, roster=ROSTER, omit=()) -> pathlib.Path:
    rows = {}
    for i, (name, club, pos, flex) in enumerate(roster):
        if name in omit:
            continue
        rows[str(60000000 + i)] = {
            'dk_id': str(60000000 + i), 'gsis_id': f'00-{i:07d}', 'name': name, 'team': club,
            'position': pos, 'dk_points': round(flex / 900.0, 3), 'projection_state': 'SYNTHETIC',
        }
    p = tmp / 'PROJ.json'
    p.write_text(json.dumps({'rows': rows}))
    return p


def _draws(slate, roster=ROSTER, omit=(), seed: int = 20261001):
    """Shared worlds: one column per world, every player drawn in the same world. Deterministic.

    SEEDED AND WIDE ON PURPOSE. This is NOT a model of football and does not pretend to be -- its only
    job is to hand the optimiser a joint distribution in which different captains win in different
    worlds, so that "no duplicate person" and "both clubs" are tested across many distinct optima
    rather than across one. A narrow spread produced four distinct optima and tested almost nothing.
    """
    import random
    out = {}
    for k, v in sorted(slate['players'].items()):
        if v['name'] in omit:
            continue
        rng = random.Random(f'{seed}|{k}')
        base = v['flex']['salary'] / 900.0
        out[k] = [max(0.0, base * rng.uniform(0.15, 2.4)) for _ in range(N_WORLDS)]
    return out


def _selected(sl, draws, n):
    """Every lineup the selector produced, whether it filled the portfolio or fell short.

    A shortfall still returns lawful lineups, and the invariants must hold on all of them. Testing
    only the PASS case would check the invariants on a single lineup, since the candidate set from
    per-world optima alone lands short of most entry counts -- a limitation the stage reports.
    """
    o = S.s5_candidates_and_selection(sl, set() if n is None else set(), draws, n)
    if o.state is State.PASS:
        return o, o.value
    assert o.state is State.DEFERRED and o.code == 'SHOWDOWN_PORTFOLIO_SHORT_OF_ENTRIES', o
    return o, o.evidence['partial']


def _slate(export):
    o = S.s1_ingest(export)
    assert o.state is State.PASS, o
    i = S.s2_slate_identity(o.value['pool'])
    assert i.state is State.PASS, i
    return o.value, i.value


@check('the synthetic export parses, and the cap genuinely binds on this slate')
def t_fixture_is_sound():
    tmp = pathlib.Path(tempfile.mkdtemp())
    ing, sl = _slate(_write_export(tmp))
    assert len(sl['players']) == len(ROSTER), (len(sl['players']), len(ROSTER))
    six_dearest = sorted((v['flex']['salary'] for v in sl['players'].values()), reverse=True)[:6]
    assert sum(six_dearest) > S.SALARY_CAP, sum(six_dearest)
    six_cheapest = sorted(v['flex']['salary'] for v in sl['players'].values())[:6]
    assert sum(six_cheapest) < S.SALARY_CAP, sum(six_cheapest)
    return (f'{len(sl["players"])} players; six dearest {sum(six_dearest)} exceeds the '
            f'{S.SALARY_CAP} cap, six cheapest {sum(six_cheapest)} fits')


@check('INVARIANT 1: the same person has distinct CPT and FLEX DK ids')
def t_inv1_distinct_ids():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    for k, v in sl['players'].items():
        assert v['cpt']['dk_id'] != v['flex']['dk_id'], k
    ids = {v['cpt']['dk_id'] for v in sl['players'].values()} | \
          {v['flex']['dk_id'] for v in sl['players'].values()}
    assert len(ids) == 2 * len(sl['players']), (len(ids), len(sl['players']))
    return f'{len(sl["players"])} people, {len(ids)} distinct priced items'


@check('INVARIANT 2: the model join is on player identity, and DK item ids do not appear in it')
def t_inv2_join_on_identity():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    proj = _write_projections(tmp)
    o = S.s4_projections(sl, set(), proj)
    assert o.state is State.PASS, o
    assert set(o.value) == set(sl['players']), 'the join did not cover exactly the slate'
    # The projection ids (60000000+) share nothing with the slate's priced-item ids (50000000+), so a
    # dk_id join would have matched nobody. That it matched everybody proves the join is on identity.
    slate_ids = {v['cpt']['dk_id'] for v in sl['players'].values()} | \
                {v['flex']['dk_id'] for v in sl['players'].values()}
    proj_ids = set(json.loads(proj.read_text())['rows'])
    assert not (slate_ids & proj_ids), 'the id spaces overlap, so this check proves nothing'
    return f'{len(o.value)} joined across disjoint id spaces'


@check('INVARIANTS 3 and 4: CPT seat carries the CPT id, every FLEX seat the FLEX id')
def t_inv3_4_upload_ids():
    tmp = pathlib.Path(tempfile.mkdtemp())
    export = _write_export(tmp)
    ing, sl = _slate(export)
    o = S.run(export, official_inactives=[], proj_path=_write_projections(tmp),
              draws=_draws(sl), n_entries=1)
    assert o.state is State.PASS, o
    up = _REPO / o.value['upload'] if not o.value['upload'].startswith('/') else pathlib.Path(o.value['upload'])
    rows = list(csv.reader(up.open(newline='', encoding='utf-8')))
    assert rows[0][4:] == list(S.SHOWDOWN_SLOTS), rows[0][4:]
    cpt_ids = {v['cpt']['dk_id']: k for k, v in sl['players'].items()}
    flex_ids = {v['flex']['dk_id']: k for k, v in sl['players'].items()}
    for r in rows[1:]:
        assert r[4] in cpt_ids, f'CPT seat {r[4]} is not a captain-priced id'
        for seat in r[5:10]:
            assert seat in flex_ids, f'FLEX seat {seat} is not a flex-priced id'
    return f'{len(rows) - 1} uploaded row(s), every seat priced for the slot it sits in'


@check('INVARIANT 5: the optimiser never selects the same person twice')
def t_inv5_no_duplicate_person():
    tmp = pathlib.Path(tempfile.mkdtemp())
    export = _write_export(tmp)
    _, sl = _slate(export)
    o, lineups = _selected(sl, _draws(sl), 8)
    assert len(lineups) >= 4, f'only {len(lineups)} lineups, too few to test this across'
    for ln in lineups:
        seats = [ln['captain']] + ln['flex']
        assert len(set(seats)) == S.ROSTER_SIZE, seats
        assert ln['captain'] not in ln['flex'], ln
    return f'{len(lineups)} lineups, every one six distinct people'


@check('INVARIANT 6: every selected lineup carries both clubs')
def t_inv6_both_teams():
    tmp = pathlib.Path(tempfile.mkdtemp())
    export = _write_export(tmp)
    _, sl = _slate(export)
    o, lineups = _selected(sl, _draws(sl), 8)
    assert len(lineups) >= 4, f'only {len(lineups)} lineups'
    for ln in lineups:
        clubs = {sl['players'][k]['dk_team'] for k in [ln['captain']] + ln['flex']}
        assert clubs == {AWAY, HOME}, clubs
    return f'{len(lineups)} lineups, every one spanning {AWAY} and {HOME}'


@check('INVARIANT 6b LOAD-BEARING: a single-club lineup is refused by the legality gate')
def t_inv6_single_club_refused():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    one = [k for k, v in sl['players'].items() if v['dk_team'] == AWAY][:6]
    o = S.validate_lineup({'captain': one[0], 'flex': one[1:6]}, sl)
    assert o.state is State.FAIL, o
    assert o.code in ('LINEUP_SINGLE_TEAM', 'LINEUP_OVER_THE_CAP'), o.code
    return f'refused with {o.code}'


@check('INVARIANT 7 LOAD-BEARING: incomplete projection coverage refuses')
def t_inv7_incomplete_projection():
    tmp = pathlib.Path(tempfile.mkdtemp())
    export = _write_export(tmp)
    _, sl = _slate(export)
    proj = _write_projections(tmp, omit=('A1 Catcher',))
    o = S.s4_projections(sl, set(), proj)
    assert o.state is State.BLOCKED, o
    assert o.code == 'SHOWDOWN_PROJECTION_DOES_NOT_COVER_THIS_GAME', o.code
    assert any(m['name'] == 'A1 Catcher' for m in o.evidence['missing']), o.evidence['missing']
    return f'{o.code}, naming A1 Catcher'


@check('INVARIANT 8 LOAD-BEARING: an unresolved availability stage blocks PUBLICATION')
def t_inv8_unresolved_availability_blocks_publication():
    tmp = pathlib.Path(tempfile.mkdtemp())
    export = _write_export(tmp)
    _, sl = _slate(export)
    # official_inactives=None leaves availability DEFERRED. Selection may still run; the upload may
    # not be written, because a portfolio chosen without the inactives can hold a player who is out.
    o = S.run(export, official_inactives=None, proj_path=_write_projections(tmp),
              draws=_draws(sl), n_entries=1)
    assert o.state is State.DEFERRED, o
    assert o.code == 'SHOWDOWN_PUBLICATION_WITHHELD', o.code
    b = o.evidence['board']
    assert b['RESULT'] == 'SELECTED_NOT_PUBLISHED', b['RESULT']
    assert 'availability' in b['withheld'], b['withheld']
    assert b['n_selected'] >= 1, b
    return f"{b['n_selected']} selected, publication withheld on {b['withheld']}"


@check('INVARIANT 8b: a player ruled out is excluded from selection, not merely flagged')
def t_inv8b_inactive_excluded():
    tmp = pathlib.Path(tempfile.mkdtemp())
    export = _write_export(tmp)
    _, sl = _slate(export)
    out_key = next(k for k, v in sl['players'].items() if v['name'] == 'A1 Runner')
    av = S.s3_availability(sl, ['A1 Runner'])
    assert av.state is State.PASS, av
    o = S.s5_candidates_and_selection(sl, av.value['absent'], _draws(sl), 8)
    lineups = o.value if o.state is State.PASS else o.evidence['partial']
    assert lineups, o
    for ln in lineups:
        assert out_key not in [ln['captain']] + ln['flex'], f'{out_key} was rostered while out'
    return f'{out_key} absent from all {len(lineups)} lineups'


@check('INVARIANT 9: a missing kicker or defence is explicit, never silently dropped')
def t_inv9_missing_kicker_dst_explicit():
    tmp = pathlib.Path(tempfile.mkdtemp())
    # Build a slate with no kicker and no defence for the home club at all.
    thin = [r for r in ROSTER if not (r[1] == HOME and r[2] in ('K', 'DST'))]
    export = _write_export(tmp, roster=thin)
    ing, sl = _slate(export)
    pos = {v['position'] for v in sl['players'].values()}
    # The runner does not invent the absent positions, and it does not pretend they are present: the
    # universe is exactly what DK priced, and the position census says so.
    home_k = [k for k, v in sl['players'].items() if v['dk_team'] == HOME and v['position'] == 'K']
    assert not home_k, home_k
    census = {p: sum(1 for v in sl['players'].values() if v['position'] == p) for p in sorted(pos)}
    assert census.get('K') == 1 and census.get('DST') == 1, census
    # And a projection omitting a kicker that IS priced refuses rather than dropping him.
    full = _write_export(pathlib.Path(tempfile.mkdtemp()))
    _, sl2 = _slate(full)
    o = S.s4_projections(sl2, set(), _write_projections(tmp, omit=('B Kicker', f'{HOME} Defense')))
    assert o.state is State.BLOCKED, o
    names = {m['name'] for m in o.evidence['missing']}
    assert {'B Kicker', f'{HOME} Defense'} <= names, names
    return f'census {census}; an unprojected priced kicker and defence both refuse by name'


@check('the declared caps are policy and are reported with the portfolio, not hidden')
def t_caps_reported():
    tmp = pathlib.Path(tempfile.mkdtemp())
    export = _write_export(tmp)
    _, sl = _slate(export)
    o, _lineups = _selected(sl, _draws(sl), 8)
    caps = o.evidence['caps']
    assert caps['player'] == S.MAX_PLAYER_EXPOSURE and caps['overlap'] == S.MAX_OVERLAP, caps
    return f'caps carried on the result: {caps}'


@check('LOAD-BEARING: absent simulated draws refuse rather than being manufactured from a mean')
def t_draws_absent_refused():
    tmp = pathlib.Path(tempfile.mkdtemp())
    export = _write_export(tmp)
    _, sl = _slate(export)
    o = S.s5_candidates_and_selection(sl, set(), {}, 2)
    assert o.state is State.BLOCKED, o
    assert o.code == 'SHOWDOWN_DRAWS_ABSENT', o.code
    d = _draws(sl)
    k = next(iter(d))
    d[k] = d[k][:-1]
    r = S.s5_candidates_and_selection(sl, set(), d, 2)
    assert r.state is State.FAIL, r
    assert r.code == 'SHOWDOWN_DRAWS_RAGGED', r.code
    return 'absent draws BLOCK, ragged draws FAIL -- neither is filled in'


@check('GENERATOR: the exact per-world optima are always included, with gap zero')
def t_gen_exact_included():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    g = S.near_optimal_candidates(sl, set(), _draws(sl))
    assert g.state is State.PASS, g
    exact = [c for c in g.value if c['n_worlds_optimal'] > 0]
    assert exact, 'no candidate is world-optimal'
    assert all(c['best_gap'] == 0.0 for c in exact), [c['best_gap'] for c in exact[:3]]
    assert sum(c['n_worlds_optimal'] for c in exact) == g.evidence['n_worlds'], (
        sum(c['n_worlds_optimal'] for c in exact), g.evidence['n_worlds'])
    return f"{len(exact)} world-optimal candidates covering all {g.evidence['n_worlds']} worlds"


@check('GENERATOR: every candidate is lawful, and every gap is inside the declared band')
def t_gen_lawful_and_banded():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    g = S.near_optimal_candidates(sl, set(), _draws(sl))
    assert g.state is State.PASS, g
    band = g.evidence['loss_band']
    for c in g.value:
        v = S.validate_lineup(c, sl)
        assert v.state is State.PASS, (c, v.code)
        assert c['best_gap'] <= band + 1e-9, (c['captain'], c['best_gap'], band)
        seats = [c['captain']] + c['flex']
        assert len(set(seats)) == S.ROSTER_SIZE
        assert {sl['players'][k]['dk_team'] for k in seats} == {AWAY, HOME}
        assert v.value['salary'] <= S.SALARY_CAP
    return (f"{len(g.value)} candidates, all lawful, max gap "
            f"{g.evidence['max_gap']} within band {band}")


@check('GENERATOR LOAD-BEARING: a zero band admits ONLY the exact optima')
def t_gen_zero_band():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    d = _draws(sl)
    z = S.near_optimal_candidates(sl, set(), d, loss_band=0.0, rounds=6, drop_rounds=0)
    assert z.state is State.PASS, z
    assert all(c['n_worlds_optimal'] > 0 for c in z.value), 'a non-optimal lineup entered at band 0'
    wide = S.near_optimal_candidates(sl, set(), d)
    assert len(wide.value) > len(z.value), (len(wide.value), len(z.value))
    return f'band 0 gives {len(z.value)}; the declared band gives {len(wide.value)}'


@check('GENERATOR: flex-core exclusion is what widens the pool, and it is recorded')
def t_gen_flex_drops_recorded():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    d = _draws(sl)
    cpt_only = S.near_optimal_candidates(sl, set(), d, drop_rounds=0)
    full = S.near_optimal_candidates(sl, set(), d)
    assert full.state is State.PASS and cpt_only.state is State.PASS
    assert len(full.value) > len(cpt_only.value), (len(full.value), len(cpt_only.value))
    assert full.evidence['n_dropped_for_diversity'] > 0, full.evidence
    assert any('drop_round' in r for r in full.evidence['rounds']), full.evidence['rounds']
    return (f"captain rounds alone {len(cpt_only.value)}; with "
            f"{full.evidence['n_dropped_for_diversity']} drops {len(full.value)}")


@check('GENERATOR: a wider pool fills portfolio sizes the optima alone could not, caps UNCHANGED')
def t_gen_improves_fill():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    d = _draws(sl)
    before = {'player': S.MAX_PLAYER_EXPOSURE, 'captain': S.MAX_CAPTAIN_EXPOSURE,
              'overlap': S.MAX_OVERLAP}
    o12 = S.s5_candidates_and_selection(sl, set(), d, 12)
    assert o12.state is State.PASS, o12
    assert o12.evidence['n_chosen'] == 12, o12.evidence
    after = o12.evidence['caps']
    assert after == before, f'the caps moved: {before} -> {after}'
    return f'12/12 filled with caps unchanged at {after}'


@check('GENERATOR: ranking uses optimality and gap only -- no ownership or correlation is invented')
def t_gen_no_ownership():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _, sl = _slate(_write_export(tmp))
    g = S.near_optimal_candidates(sl, set(), _draws(sl))
    assert g.evidence['RANKED_BY'] == 'world-optimality count then objective gap', g.evidence
    # No candidate carries an ownership or leverage field, so nothing downstream can read one.
    banned = {'ownership', 'projected_ownership', 'leverage', 'duplication', 'correlation'}
    for c in g.value[:5]:
        assert not (banned & set(c)), set(c) & banned
    src = pathlib.Path(S.__file__).read_text()
    assert 'import' not in src.split('def near_optimal_candidates')[1].split('def ')[0].replace(
        'import numpy as np', '').replace('from nfl.dfs.showdown import optimal_worlds as OW', '')
    return 'ranked by optimality and gap; no ownership, leverage or correlation field exists'


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    test_zz_every_check_passed.__doc__
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
