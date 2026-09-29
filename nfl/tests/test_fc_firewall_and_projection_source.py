#!/usr/bin/env python3.12
"""The FC firewall and the projection-source contract, as executable checks.

The firewall test is the important one. A comment saying "do not use this for features"
is not a firewall; a module that refuses to return values to a proprietary caller is.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import fc_context as FC  # noqa: E402
from nfl.tools import portfolio_audit as PA  # noqa: E402
from nfl.tools import projection_source as PS  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

from nfl.tests import _registry  # noqa: E402

#: RUN THIS MODULE IN A FRESH INTERPRETER. run_suite reads this from source and re-runs the
#: module through itself in a subprocess, so it is judged by identical logic.
REQUIRES_OWN_PROCESS = 'the FantasyCruncher firewall in dk_universe refuses to return external values if ANY proprietary projection module is imported in this interpreter -- that refusal IS the guarantee that FantasyCruncher cannot become a feature input, so this test is only meaningful in a fresh process'

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('FIREWALL: fc_context refuses to return values to a proprietary caller')
def t_firewall_runtime():
    clean = subprocess.run(
        [sys.executable, '-c',
         'import sys; sys.path.insert(0,"."); from nfl.tools import fc_context as F;'
         'r=F.load(); print(r.state.value, r.code, len(r.value) if r.state.value=="PASS"'
         ' else 0)'],
        cwd=_REPO, capture_output=True, text=True)
    dirty = subprocess.run(
        [sys.executable, '-c',
         'import sys; sys.path.insert(0,"."); import nfl.production.nonqb.inactives;'
         'from nfl.tools import fc_context as F; r=F.load();'
         'print(r.state.value, r.code, len(r.value) if r.state.value=="PASS" else 0)'],
        cwd=_REPO, capture_output=True, text=True)
    assert 'PASS FC_CONTEXT_LOADED 273' in clean.stdout, clean.stdout + clean.stderr
    assert 'FAIL FC_READ_FROM_PROPRIETARY_CONTEXT 0' in dirty.stdout, \
        dirty.stdout + dirty.stderr
    return ('a clean process gets 273 rows; a process holding nfl.production gets FAIL '
            'and zero values. The refusal is the firewall, not the docstring')


@check('FIREWALL: no proprietary module imports fc_context')
def t_firewall_static():
    hits = []
    for prefix in PS.FC.PROPRIETARY_PREFIXES:
        d = _REPO / prefix.replace('.', '/')
        if not d.exists():
            continue
        for p in d.rglob('*.py'):
            txt = p.read_text(errors='ignore')
            if 'fc_context' in txt:
                hits.append(str(p.relative_to(_REPO)))
    assert not hits, f'proprietary modules referencing fc_context: {hits}'
    return f'{len(PS.FC.PROPRIETARY_PREFIXES)} proprietary prefixes scanned, zero imports'


@check('BLENDED_RESEARCH_MODE is defined and unreachable')
def t_blended_refused():
    post = json.loads(
        (_REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json').read_text())
    p = next(iter(post['players'].values()))
    assert PS.MODE_BLENDED in PS.MODES, 'mode not declared'
    assert PS.MODE_BLENDED not in PS.AUTHORISED_TODAY, 'blended is authorised'
    try:
        PS.resolve(p, mode_preference=PS.MODE_BLENDED)
    except PS.BlendedModeRefused:
        return 'declared in MODES, absent from AUTHORISED_TODAY, resolve() raises on it'
    raise AssertionError('resolve() accepted BLENDED_RESEARCH_MODE')


@check('a missing projection is UNAVAILABLE, never zero')
def t_never_zero():
    r = PS.run()
    assert r.state is State.PASS, str(r)
    recs = list(r.value['records'].values())
    assert len(recs) == 457, len(recs)
    unav = [x for x in recs if x['projection_mode'] == PS.MODE_UNAVAILABLE]
    assert len(unav) == 184, len(unav)
    for x in unav:
        for f in ('mean', 'median', 'p75', 'p90', 'floor', 'ceiling'):
            assert x[f] == PS.MODE_UNAVAILABLE, f'{x["player"]} {f}={x[f]!r}'
    g = PS.assert_no_silent_zero(recs)
    assert g.state is State.PASS, str(g)
    return f'{len(unav)} unavailable records, every numeric field the sentinel not 0.0'


@check('every external number is labelled non-proprietary with its source')
def t_fallback_labelled():
    r = PS.run()
    recs = list(r.value['records'].values())
    fb = [x for x in recs if x['projection_mode'] == PS.MODE_FC_FALLBACK]
    assert len(fb) == 273, len(fb)
    for x in fb:
        assert x['is_proprietary'] is False
        assert 'FantasyCruncher' in (x['source'] or '')
        assert 'NOT_OUR_MODEL' in x
    assert r.value['mode_counts'].get(PS.MODE_PROPRIETARY, 0) == 0
    assert 'may NOT be described as proprietary' in \
        r.value['MODE_AUTHORISATION']['slate_is_not_proprietary']
    g = PS.assert_fallback_is_labelled(recs)
    assert g.state is State.PASS, str(g)
    return f'{len(fb)} fallback records labelled; zero proprietary numbers on this slate'


@check('no rosterable position silently disappears; K is declared not discovered')
def t_positions():
    r = PS.run()
    m = {row['position']: row for row in r.value['readiness_matrix']}
    for pos in ('QB', 'RB', 'WR', 'TE', 'DST'):
        assert pos in m, f'{pos} missing from the readiness matrix'
        assert m[pos]['rosterable_players'] > 0
        assert m[pos]['blocker'], f'{pos} has no declared blocker'
    assert m['DST']['blocker'] == 'NEVER_IMPLEMENTED', m['DST']['blocker']
    assert 'K' in m and m['K']['blocker'].startswith('NOT_REQUIRED_BY_THIS_SLATE')
    assert all(row['simulation_ready_pct'] in (0.0, None)
               for row in r.value['readiness_matrix']), \
        'a position claims simulation readiness with no distribution'
    return ('5 rosterable positions present with declared blockers; DST recorded as '
            'NEVER_IMPLEMENTED; K declared in advance; simulation-ready 0% everywhere')


@check('the 48 placeholder lineups are legal and carry no reported-inactive player')
def t_portfolio_legal():
    r = PA.run()
    assert r.state is State.PASS, str(r)
    v = r.value
    assert len(v['lineups']) == 48
    assert v['contest_allocation']['matches'] is True, v['contest_allocation']
    ls = v['legality_summary']
    assert ls['n_reported_inactive_in_any_lineup'] == 0, ls['issue_codes']
    assert ls['issue_codes'] == {}, ls['issue_codes']
    for eid, d in v['lineups'].items():
        assert d['salary'] <= PA.SALARY_CAP, f'{eid} salary {d["salary"]}'
        assert len(d['roster']) == 9, f'{eid} has {len(d["roster"])} slots'
        assert all(c['dk_id'] for c in d['roster']), f'{eid} has a blank slot'
    return ('48 lineups, 2/20/6/20 allocation, every salary within cap, nine filled '
            'slots each, zero reported-inactive players rostered')


@check('the audit is read-only: the placeholder file is byte-unchanged')
def t_read_only():
    before = PA._digest(PA.PLACEHOLDERS)
    PA.run()
    after = PA._digest(PA.PLACEHOLDERS)
    assert before == after, 'the audit modified the owner placeholder file'
    out = json.loads(PA.OUT.read_text())
    assert 'does not modify' in out['READ_ONLY']
    assert out['source_files']['placeholders']['sha256'] == before
    return f'placeholder digest {before[:16]} unchanged across a full audit run'


@check('exposure arithmetic is internally consistent')
def t_exposure():
    r = PA.run()
    exp = r.value['exposure']
    assert exp['n_lineups'] == 48
    total = sum(e['n'] for e in exp['player_exposure'].values())
    assert total == 48 * 9, f'{total} roster slots counted, expected 432'
    qb = sum(e['n'] for e in exp['qb_exposure'].values())
    dst = sum(e['n'] for e in exp['dst_exposure'].values())
    assert qb == 48, f'{qb} QB slots'
    assert dst == 48, f'{dst} DST slots'
    assert 0 < exp['mean_pairwise_overlap'] < 9
    return (f'432 slots, 48 QB, 48 DST, mean pairwise overlap '
            f'{exp["mean_pairwise_overlap"]}/9')


@check('the role-evidence diagnostic never calls itself a projection disagreement')
def t_diagnostic_labelling():
    r = PA.run()
    diag = r.value['role_evidence_diagnostic']
    assert diag, 'no diagnostics produced at all'
    for d in diag:
        assert d['LABEL'] == 'ROLE_EVIDENCE_DIAGNOSTIC'
        assert 'NOT_A_PROJECTION_DISAGREEMENT' in d
        assert 'fc_projection_external_only' in d
        assert 'our_projection' not in d and 'claude_projection' not in d
    return (f'{len(diag)} diagnostics, every one labelled ROLE_EVIDENCE_DIAGNOSTIC with '
            f'no claimed projection of ours')


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
