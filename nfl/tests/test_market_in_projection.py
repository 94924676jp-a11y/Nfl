#!/usr/bin/env python3.12
"""Where, and how much, does the sportsbook move a proprietary forecast? Measured, not asserted.

The owner's governance position is that no sportsbook price may enter proprietary prediction. The
code currently does let it in, in three places, and the right first move is to MEASURE each one
rather than to rip them out minutes before a lock -- removing them changes every projection and
every baseline earlier work was validated against, which is an owner decision.

So these checks are CHARACTERISATION checks. They record the measured sensitivity of each layer to
the market, per layer, so the size of the decision is visible. They are written so that when the
owner rules "football evidence only", the assertions flip from "this is the sensitivity" to "this is
zero" by changing the expected value, not by rewriting the test.

WHY THIS MODULE EXISTS AT ALL: the claim "the kicker is conditioned on the implied total" was made
in an audit, from reading `kicker_model.project`'s SIGNATURE, which accepts `club_implied` and
`opponent_implied`. The body references neither. A signature is not a dependence, and the only
defence against that mistake is executing the thing.
"""
from __future__ import annotations

import ast
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import kicker_model, market_response  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _body_names(module_rel, fn_name):
    """Every bare Name a function's body actually references. A signature is not a dependence."""
    t = ast.parse((_REPO / module_rel).read_text())
    fn = next(n for n in ast.walk(t) if isinstance(n, ast.FunctionDef) and n.name == fn_name)
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


# ------------------------------------------------------------------ kicker: NOT market-dependent

@check('kicker_model.project accepts implied totals and uses NEITHER of them')
def _kicker_params_dead():
    t = ast.parse((_REPO / 'nfl/tools/kicker_model.py').read_text())
    fn = next(n for n in ast.walk(t) if isinstance(n, ast.FunctionDef) and n.name == 'project')
    params = [a.arg for a in fn.args.args]
    used = _body_names('nfl/tools/kicker_model.py', 'project')
    assert 'club_implied' in params and 'opponent_implied' in params, params
    assert 'club_implied' not in used, 'club_implied IS used -- this check is now stale'
    assert 'opponent_implied' not in used, 'opponent_implied IS used -- this check is now stale'
    return (f'signature takes {params}, body references neither implied argument: '
            'the kicker is NOT market-dependent')


@check('a kicker projection is byte-identical under wildly different implied totals')
def _kicker_insensitive():
    o = kicker_model.load() if hasattr(kicker_model, 'load') else None
    m = (o.value if hasattr(o, 'value') else o) if o is not None else kicker_model.measure()
    m = m.value if hasattr(m, 'value') else m
    club = next(c for c in ('PIT', 'CLE', 'KC', 'BUF') if (m['per_club_season'].get(c) or {}))
    lo = kicker_model.project(club, m, opponent_implied=3.0, club_implied=3.0)
    hi = kicker_model.project(club, m, opponent_implied=45.0, club_implied=45.0)
    assert lo == hi, (lo.get('dk_points'), hi.get('dk_points'))
    return (f"{club} kicker identical at implied 3.0 and 45.0 "
            f"(dk_points {lo.get('dk_points')}) -- no market path to remove")


# ---------------------------------------------------------- team volume: measured, and it is small

@check('team volume DOES respond to the market, and the response is measured on the DEVIATION')
def _volume_responds():
    coef = market_response.load()
    coef = coef.value if hasattr(coef, 'value') else coef
    c = coef['coef'] if 'coef' in coef else coef
    fld = next((f for f in ('plays', 'dropbacks', 'pass_attempts') if f in c), None)
    assert fld, sorted(c)[:8]
    base_cm = {'this_total_line': 44.0, 'this_favoured_by': 3.0,
               'baseline_mean_total_line': 44.0, 'baseline_mean_favoured_by': 3.0,
               'n_baseline_games': 20}
    at_baseline, acct0 = market_response.adjust(fld, 80.0, base_cm, c)
    assert abs(at_baseline - 80.0) < 1e-9, (at_baseline, acct0)

    moved = dict(base_cm, this_total_line=54.0)
    shifted, acct = market_response.adjust(fld, 80.0, moved, c)
    delta = shifted - 80.0
    assert abs(delta) > 1e-9, 'a 10-point total move produced no change -- gate may be off'
    return (f"{fld}: an AVERAGE line moves the baseline by exactly 0.0 (so the market is not "
            f"counted twice); a +10.0 total-line deviation moves 80.0 -> {shifted:.4f} "
            f"({delta:+.4f}, {delta / 80.0:+.2%})")


@check('the volume response is small relative to the level -- the decision is cheap here')
def _volume_small():
    coef = market_response.load()
    coef = coef.value if hasattr(coef, 'value') else coef
    c = coef['coef'] if 'coef' in coef else coef
    fld = next(f for f in ('plays', 'dropbacks', 'pass_attempts') if f in c)
    cm = {'this_total_line': 38.5, 'this_favoured_by': 2.5,
          'baseline_mean_total_line': 43.5, 'baseline_mean_favoured_by': -0.75,
          'n_baseline_games': 20}
    adj, acct = market_response.adjust(fld, 79.6471, cm, c)
    frac = abs(adj - 79.6471) / 79.6471
    assert frac < 0.05, f'{frac:.2%} is larger than the 5% this check was written against'
    return (f"{fld} 79.6471 -> {adj:.4f} on tonight's actual deviations "
            f"({frac:.2%} of the level; cap_binding={acct.get('cap_fraction') is not None and acct.get('cap_binding')})")


@check('an UNKNOWN line leaves the baseline alone and is not read as an average line')
def _unknown_line_not_average():
    coef = market_response.load()
    coef = coef.value if hasattr(coef, 'value') else coef
    c = coef['coef'] if 'coef' in coef else coef
    fld = next(f for f in ('plays', 'dropbacks', 'pass_attempts') if f in c)
    cm = {'this_total_line': None, 'this_favoured_by': None,
          'baseline_mean_total_line': 43.5, 'baseline_mean_favoured_by': -0.75}
    adj, acct = market_response.adjust(fld, 80.0, cm, c)
    assert adj == 80.0, adj
    assert acct['state'] == 'NOT_ADJUSTED', acct
    assert 'NOT_ZERO' in acct, acct
    return f"state={acct['state']}, and the artifact says why: {acct['NOT_ZERO'][:60]}..."


# ------------------------------------------- touchdown pool and DST: the two material dependences

@check('the club touchdown pool IS a function of the market implied total')
def _td_pool_market():
    used = _body_names('nfl/tools/proj_v1.py', 'build')
    src = (_REPO / 'nfl/tools/proj_v1.py').read_text()
    assert 'td_rates.expected_team_td(imp' in src, 'TD pool call site changed'
    assert 'implied' in str(used) or 'imp' in used, sorted(used)[:10]
    return ('team_expected_td = td_rates.expected_team_td(implied_total, ...) -- MATERIAL '
            'dependence, confirmed at the call site, not inferred from a docstring')


@check('the DST points-allowed distribution is CENTRED on the market implied total')
def _dst_market():
    from nfl.tools import dst_model
    used = _body_names('nfl/tools/dst_model.py', 'pa_expectation')
    assert 'implied_allowed' in used, sorted(used)
    src = (_REPO / 'nfl/tools/dst_model.py').read_text()
    assert 'pts = implied_allowed + r' in src, 'pa_expectation formula changed'
    none_val, acct = dst_model.pa_expectation(None, {'state': 'MEASURED', 'residuals': [0.0]})
    assert none_val is None and acct['state'] == 'NOT_COMPUTABLE', acct
    return ('every points-allowed world is implied_allowed + residual, so the whole distribution '
            'moves with the line. MATERIAL. With no line it refuses rather than assuming one')


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
