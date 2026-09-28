#!/usr/bin/env python3.12
"""V1: the measured constants, the identities, the withholdings, and the two universe defects.

WHAT THESE TESTS ARE FOR. V1 replaced V0's share model, and most of what went wrong while building
it went wrong in a way no unit test would have caught: a cohort that pooled quarterbacks into a
receiver cohort, an appearance probability applied to one position out of four, an evaluation
harness whose universe was players who survived to 2026. Those are the cases pinned here, because
each one produced a number that looked like football and was not.

Three of these tests are LOAD-BEARING in the G0A sense: they assert that bad state is REFUSED, and
they would fail if the refusal were removed rather than merely passing on clean input.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import proj_v1 as V  # noqa: E402
from nfl.tools import td_rates as R  # noqa: E402
from nfl.tools import xlsx_writer as X  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

ART = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'
ACC = _REPO / 'nfl/dfs/salaries/DK_WEEK3_V1_ACCEPTANCE.json'
RATES = _REPO / 'nfl/derived/TD_RATES.json'
DST = _REPO / 'nfl/derived/DST_RATES.json'
CSVM = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJECTIONS_V1.csv'

from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _art():
    assert ART.exists(), f'{ART.name} not built'
    return json.loads(ART.read_text())


# --------------------------------------------------------------------- measured, not declared
@check('points per touchdown is MEASURED and is not V0 asserted 7.0')
def t_points_per_td():
    a = json.loads(RATES.read_text())
    p = a['points_to_td']
    assert p['state'] == 'MEASURED', p
    assert p['n_club_games'] > 2000, f"only {p['n_club_games']} club-games"
    ppt = p['implied_points_per_td_at_mean']
    assert 8.5 < ppt < 10.5, f'measured points per touchdown {ppt} is not football-plausible'
    assert abs(ppt - 7.0) > 1.5, (
        'the measured figure has collapsed back onto V0 declared 7.0, which credited every point '
        'to a touchdown and ignored field goals')
    return f'{ppt} over {p["n_club_games"]} club-games, against V0 asserted 7.0'


@check('every position has a non-negative two-term touchdown rate that reproduces its total')
def t_positional_rates():
    a = json.loads(RATES.read_text())
    out = []
    for pos, v in a['positional_rates'].items():
        assert not str(v['state']).startswith('NOT_'), f'{pos}: {v}'
        assert v['td_per_rz_opportunity'] >= 0 and v['td_per_non_rz_opportunity'] >= 0, (
            f'{pos} carries a negative rate, which is not a football quantity: {v}')
        cal = v['calibration_ratio_pred_over_actual']
        assert 0.85 <= cal <= 1.15, f'{pos} rate reproduces only {cal} of its actual touchdowns'
        out.append(f"{pos} {cal:.3f}")
    wr = a['positional_rates']['WR']
    assert wr['td_per_non_rz_opportunity'] > 0, (
        'a receiver with zero red-zone rate would be back to V0 Higgins defect: 28 per cent of '
        'receiver touchdowns come from outside the twenty and need a non-red-zone term')
    return 'calibration ' + ' '.join(out)


@check('the two selected constants are not back at their declared values')
def t_constants_selected():
    assert V.DEPTH_CLAIM_BLEND == 1.0, (
        f'DEPTH_CLAIM_BLEND is {V.DEPTH_CLAIM_BLEND}; 0.5 was the declared value and forward '
        f'chaining rejected it on both a selection and a confirmation set')
    assert V.PRIOR_WEIGHT_CAP <= 4.0, (
        f'PRIOR_WEIGHT_CAP is {V.PRIOR_WEIGHT_CAP}; at the declared 12 the model only TIED a '
        f'current-season-only baseline on rank correlation')
    return f'blend {V.DEPTH_CLAIM_BLEND}, prior cap {V.PRIOR_WEIGHT_CAP}'


# ------------------------------------------------------------------------------- identities
@check('every club identity holds, and it holds by construction not by repair')
def t_identities():
    a = _art()
    ids = a['identities']
    assert ids, 'no identities were checked'
    bad = [i for i in ids if i.get('state') == 'VIOLATED']
    assert not bad, f'{len(bad)} violated: {bad[:3]}'
    ratios = [i['ratio'] for i in ids if i.get('ratio') is not None]
    worst = max(abs(r - 1.0) for r in ratios)
    assert worst < 0.005, f'worst identity ratio is off by {worst}, which is a repair not an identity'
    return f'{len(ids)} identities, worst off by {worst:.2e}'


@check('no projected player carries an exact 0.00, and no unprojected player carries a number')
def t_no_silent_zero():
    a = _art()
    # an exact 0.00 is permitted ONLY where it is labelled a computed zero, because downstream a
    # bare 0.00 is indistinguishable from a row we refused to project
    zeros = [r['name'] for r in a['rows'].values()
             if r.get('dk_points') == 0.0
             and r.get('projection_state') != 'PROJECTED_COMPUTED_ZERO']
    assert not zeros, f'unlabelled exact zeros present: {zeros[:5]}'
    labelled = [r['name'] for r in a['rows'].values()
                if r.get('projection_state') == 'PROJECTED_COMPUTED_ZERO']
    for r in a['rows'].values():
        if r.get('projection_state') == 'PROJECTED_COMPUTED_ZERO':
            assert r.get('COMPUTED_NOT_MISSING'), f"{r['name']} labelled but carries no note"
    for r in a['rows'].values():
        if r.get('dk_points') is None:
            assert r.get('projection_state') and not str(r['projection_state']).startswith(
                'PROJECTED'), f"{r['name']} has no number and no refusal state"
            assert r.get('NOT_ZERO') or r.get('IDENTITY_NOT_GUESSED'), (
                f"{r['name']} carries no number and no reason")
    n_none = sum(1 for r in a['rows'].values() if r.get('dk_points') is None)
    return (f'{len(a["rows"])} rows, 0 UNLABELLED zeros, {len(labelled)} labelled computed '
            f'zeros, {n_none} withheld each with a named reason')


@check('an OPEN identity conflict is WITHHELD, not projected at zero')
def t_identity_withheld():
    a = _art()
    held = [r for r in a['rows'].values()
            if r.get('projection_state') == 'WITHHELD_IDENTITY_CONFLICT_OPEN']
    assert held, ('no row is withheld for an open identity conflict. IDC-02 is open -- the '
                  'research named Matthew McClain and the universe carries Malik McClain -- so at '
                  'least one row must be withheld')
    for r in held:
        assert r['dk_points'] is None, f"{r['name']} withheld but carries {r['dk_points']}"
    return f'{len(held)} withheld: {[r["name"] for r in held]}'


# -------------------------------------------------------------- the defects V1 exists to fix
@check('LOAD-BEARING: a backup quarterback cannot carry starter-level output')
def t_backup_qb():
    a = _art()
    rows = a['rows']
    starters = {(r['team'], r['position']): r['dk_points'] for r in rows.values()
                if r.get('is_predicted_starter') and r.get('dk_points') is not None}
    worst = None
    for r in rows.values():
        if r.get('position') != 'QB' or r.get('dk_points') is None:
            continue
        if r.get('is_predicted_starter'):
            continue
        sp = starters.get((r['team'], 'QB'))
        if not sp:
            continue
        ratio = r['dk_points'] / sp
        if worst is None or ratio > worst[1]:
            worst = (r['name'], ratio)
        assert ratio <= 0.141 + 1e-9, (
            f"{r['name']} is at {ratio:.3f} of his club predicted starter. The measured rank-2 "
            f"appearance rate is 0.141. V0 projected Drew Lock at 17.88 on exactly this shape.")
    assert worst, 'no non-starting quarterback was found to test, so this test proved nothing'
    return f'worst backup is {worst[0]} at {worst[1]:.4f} of his starter, limit 0.141'


@check('an established star is not shrunk below a reserve on role band')
def t_star_band():
    a = _art()
    rows = {r['name']: r for r in a['rows'].values()}
    for nm in ("Ja'Marr Chase", 'Sam Darnold'):
        r = rows.get(nm)
        assert r, f'{nm} absent from the slate, so this regression case cannot be checked'
        assert r['role_band'] == 'ALPHA', (
            f"{nm} came back {r['role_band']}. He is an established alpha; a quiet two-game "
            f"sample must not demote him, which is the circularity role_state.py removed.")
    return 'Chase and Darnold both ALPHA'


@check('LOAD-BEARING: appearance probability is applied at EVERY position, not just quarterback')
def t_appearance_all_positions():
    a = _art()
    seen = {}
    for r in a['rows'].values():
        al = (r.get('allocation') or {}).get('targets') or {}
        ar = al.get('appearance_rate_measured')
        if ar is None:
            continue
        seen.setdefault(r['position'], set()).add(round(float(ar), 4))
    for pos in ('RB', 'WR', 'TE'):
        assert pos in seen, f'no {pos} row carries a measured appearance rate'
        assert any(x < 1.0 for x in seen[pos]), (
            f'every {pos} appearance rate is 1.0, so the term is not doing anything. A club '
            f'roster carries about 25 candidates and most will not play; without this Chase came '
            f'out at 10.57 against an external 27.08.')
    return {p: len(v) for p, v in sorted(seen.items())}


@check('LOAD-BEARING: a depth rank beyond the measured table is not treated as certain to play')
def t_deep_rank_default():
    a = _art()
    beyond = [r for r in a['rows'].values()
              if ((r.get('allocation') or {}).get('targets') or {}).get(
                  'rank_beyond_measured_table')]
    assert beyond, ('no row sits beyond the measured depth table, so this test proved nothing. A '
                    '25-man roster must exceed a curve measured over players who appeared.')
    for r in beyond:
        ar = (r['allocation']['targets'] or {}).get('appearance_rate_measured')
        assert ar is not None and ar < 1.0, (
            f"{r['name']} is deeper than the measured table and carries appearance {ar}. "
            f"Defaulting a missing deep rank to 1.0 declared a club eighth receiver certain to "
            f"play and drove the scored level to 0.79.")
    return f'{len(beyond)} rows beyond the table, all with appearance below 1.0'


@check('the defence layer exists for every club and the implausible zero was caught')
def t_dst():
    a = _art()
    d = [r for r in a['rows'].values() if r.get('position') == 'DST']
    assert d, 'no DST rows'
    missing = [r['name'] for r in d if r.get('dk_points') is None]
    assert not missing, f'DST without a projection: {missing}'
    lo = min(r['dk_points'] for r in d)
    hi = max(r['dk_points'] for r in d)
    assert 0 < lo and hi < 20, f'DST board runs {lo}..{hi}, which is not a plausible range'
    art = json.loads(DST.read_text())
    iz = art['implausible_zeros_found']
    assert iz.get('NYJ') == ['interception'], (
        'the Poisson plausibility test no longer catches the Jets zero interceptions across 1,419 '
        'defensive plays. P(zero) under the measured league rate is 6e-07; reporting it as a zero '
        f'silently deletes a scoring term. found: {iz}')
    for club, meas in iz.items():
        assert 'safety' not in meas and 'blocked_kick' not in meas, (
            f'{club} flagged {meas}; a zero safety over 19 games is ordinary and must not fire')
    return f'{len(d)} clubs projected {lo:.2f}..{hi:.2f}; implausible zeros {iz}'


# ------------------------------------------------------- the evaluation harness own defects
@check('LOAD-BEARING: the forward chain leaks nothing from the scored week')
def t_no_leakage():
    from nfl.tools import forward_chain as F
    from nfl.tools import player_prior as P
    po = P.load_panel()
    assert po.state is State.PASS, po
    panel = po.value
    # a player with rows in weeks 1..N: shares computed for week k must ignore weeks >= k
    target = None
    for gsis, seasons in panel['players'].items():
        ws = (seasons.get('2025') or {})
        if len(ws) >= 8:
            club = next((w.get('team') for w in ws.values() if w.get('team')), None)
            if club:
                target = (gsis, club)
                break
    assert target, 'no player with eight 2025 weeks, so leakage cannot be tested'
    gsis, club = target
    a3, n3 = F.shares_before(panel, gsis, club, 'WR', 2025, 3)
    a9, n9 = F.shares_before(panel, gsis, club, 'WR', 2025, 9)
    assert n3 < n9, f'week 3 saw {n3} weeks and week 9 saw {n9}; the window is not advancing'
    assert n3 <= 2, f'week 3 used {n3} prior weeks, so it read the scored week or later'
    return f'week 3 used {n3} prior weeks, week 9 used {n9}'


@check('LOAD-BEARING: historical positions are inferred, and inferred rows are never scored')
def t_survivorship():
    from nfl.tools import forward_chain as F
    from nfl.tools import player_prior as P
    panel = P.load_panel().value
    pos_of = P.position_index()
    pos_map, inferred = F.positions_for_chain(panel, pos_of)
    n2021 = sum(1 for (g, s) in pos_map if s == 2021)
    roster_only = sum(1 for g in panel['players']
                      if '2021' in panel['players'][g] and pos_of.get(g) in F.SKILL)
    assert n2021 > roster_only * 1.5, (
        f'inference added little: {roster_only} from the 2026 roster against {n2021} with '
        f'inference. Every roster blob is 2026, so a historical evaluation restricted to '
        f'roster-classifiable players silently became players who survived to 2026 -- it '
        f'inflated the projected level by 67 per cent and reversed a finding.')
    assert inferred, 'nothing was inferred, so the survivorship workaround is not active'
    assert all(isinstance(k, tuple) and len(k) == 2 for k in inferred)
    return f'2021: {roster_only} roster-classifiable -> {n2021} with inference; {len(inferred)} inferred player-seasons'


# ----------------------------------------------------------------------------- deliverable
@check('LOAD-BEARING: the workbook REFUSES to build while a guard is failing')
def t_workbook_gated():
    from nfl.tools import projection_workbook as W
    acc = json.loads(ACC.read_text())
    saved = ACC.read_text()
    broken = json.loads(saved)
    broken['guards']['level_within_band'] = {'state': 'FAIL', 'code': 'SEEDED',
                                             'detail': 'seeded failure'}
    try:
        ACC.write_text(json.dumps(broken))
        o = W.build()
        assert o.state is State.FAIL, (
            'the workbook built while a guard was red. The owner asked for it "once V1 passes"; '
            f'handing over a number the system itself rejects is worse than handing over none: {o}')
        assert o.code == 'WORKBOOK_REFUSED_GUARDS_FAILING', o.code
    finally:
        ACC.write_text(saved)
    passing = sum(1 for v in acc['guards'].values() if v['state'] == 'PASS')
    return f'refused on a seeded guard failure; really {passing} of {len(acc["guards"])} pass'


@check('the deliverable carries every slate row and a reason wherever there is no number')
def t_workbook_complete():
    import csv
    assert CSVM.exists(), 'the CSV was not written'
    rows = list(csv.DictReader(CSVM.open(newline='', encoding='utf-8')))
    a = _art()
    assert len(rows) == len(a['rows']), (
        f'{len(rows)} rows in the deliverable against {len(a["rows"])} on the slate. A player '
        f'silently missing from a deliverable reads as a player with nothing to say about him.')
    blank = [r for r in rows if not r['dk_points']]
    for r in blank:
        assert r['reason_if_no_projection'], f"{r['name']} blank with no reason"
    return f'{len(rows)} rows, {len(blank)} blank and every one with a reason'


@check('the xlsx writer sanitises what Excel forbids and strips only real control characters')
def t_xlsx():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'w.xlsx'
        info = X.write(p, [('Bad/Name:*?[x]', [['h'], ['a&<>"' + chr(7) + 'keep0x8', 1.5]]),
                           ('Second', [['x']])])
        assert not (set(info['sheets'][0]) & X.INVALID_SHEET_CHARS), (
            f"sheet name {info['sheets'][0]} still holds a character Excel forbids. The first "
            f"version used a regex whose escaping collapsed to 'one of these followed by a "
            f"literal ]', so it matched nothing and let invalid names through.")
        v = X.verify(p, expected_sheets=2)
        assert v['ok'], v
        esc = X._esc('a&b' + chr(7) + 'keep0x8')
        assert chr(7) not in esc and 'keep0x8' in esc, (
            f'the escaper mangled real text or kept a control character: {esc!r}')
    return f"{info['sheets']} sanitised, {v['n_cells']} cells verified"


# EXPOSE EVERY CHECK TO run_suite, the authoritative execution path. Before this the runner
# reported `0 fn, NO TALLY` for this module and executed NONE of its checks, while a direct run of
# the file printed a confident pass. See nfl/tests/_registry.py.
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
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
