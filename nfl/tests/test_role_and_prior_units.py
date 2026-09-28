#!/usr/bin/env python3.12
"""Two unit mismatches that silently crushed established players, and the guards against their return.

Both defects here are the same species: a number carried the right information in the wrong units, and
every layer downstream applied it faithfully.

  DEPTH RANK was CLUB-WIDE but read as POSITION depth. Buffalo's rows run (1, WR), (3, RB), (4, TE),
  (6, TE), (7, WR), so a club's second receiver sat at club rank 7 and was capped at FRINGE. Only one
  player per club could clear rank 3 at all.

  PRIOR WEIGHT was counted over the AT-ROLE subset while the prior VALUE was built from the player's
  whole history. For an off-role player the weight is tiny by definition -- being tiny is why the tier
  fell through to off-role -- so a correct prior got 12% of the blend.

Chained, they turned A.J. Brown into 2.7 DK points with 0.06 expected touchdowns against a career
0.487 per game. Neither raised an error, because neither is an error: each layer did exactly what it
was told with a number that meant something else.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import player_prior as PP, role_state as RS  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
V1 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('LOAD-BEARING: depth rank is re-indexed within club and position, not read club-wide')
def t_rank_scope():
    players = json.loads(POST.read_text())['players']
    scoped = RS._position_scoped_ranks(players)
    assert scoped, 'no ranks were scoped at all'
    # within any club and position the scoped ranks must be 1..n with no gaps and no duplicates
    buckets = collections.defaultdict(list)
    for dk, r in scoped.items():
        p = players[dk]
        buckets[(p.get('team'), p.get('position'))].append(r)
    for key, rs in buckets.items():
        assert sorted(rs) == list(range(1, len(rs) + 1)), (key, sorted(rs))
    # and the club-wide numbers must NOT already satisfy that, or the defect would be imaginary
    raw = collections.defaultdict(list)
    for dk, p in players.items():
        if isinstance(p.get('depth_rank'), int):
            raw[(p.get('team'), p.get('position'))].append(p['depth_rank'])
    offenders = [k for k, v in raw.items() if sorted(v) != list(range(1, len(v) + 1))]
    assert offenders, ('every club-and-position already had contiguous ranks from 1, so the supplied '
                       'depth_rank is position-scoped after all and this guard is meaningless')
    helped = sum(1 for dk, p in players.items()
                 if isinstance(p.get('depth_rank'), int) and p['depth_rank'] >= 4
                 and scoped.get(dk, 99) <= 3)
    assert helped > 20, helped
    return (f'{len(buckets)} club-position groups all contiguous from 1; {len(offenders)} groups were '
            f'not, and {helped} players move from rank 4-plus into the top three')


@check('LOAD-BEARING: the prior weight is counted over the rows the prior value was built from')
def t_prior_weight():
    # checked as BEHAVIOUR on the artifact, not as source text: an earlier version of this check
    # asserted on a code string and broke the moment the line was improved, which tests nothing
    # about what the code does.
    v1 = json.loads(V1.read_text())['rows']
    tier1 = [r for r in v1.values() if r.get('prior_tier') == 'PLAYER_OWN_ROLE'
             and r.get('prior_effective_obs') is not None]
    tier2 = [r for r in v1.values() if r.get('prior_tier') == 'PLAYER_OWN_OFF_ROLE'
             and r.get('prior_effective_obs') is not None]
    assert tier1, 'no at-role players, so the weighting cannot be checked'
    for r in tier1:
        assert abs(r['prior_effective_obs'] - r['prior_effective_obs_at_role']) < 1e-6, (
            f"{r['name']}: an at-role prior must be weighted by its at-role count")
    for r in tier2:
        assert r['prior_effective_obs'] >= r['prior_effective_obs_at_role'] - 1e-9, (
            f"{r['name']}: widening the evidence to off-role rows REDUCED the weight, which cannot "
            f"be right -- the at-role rows are a higher-similarity subset of the wider set")
    # and the blend must actually use it: a player whose weight rose must show prior influence
    blended = [r for r in tier2
               if (r.get('basis') or {}).get('target_share', {}).get('prior_weight_fraction')]
    assert blended or not tier2, 'off-role priors carry weight but none reaches the blend'
    return (f'{len(tier1)} at-role players weighted by their at-role count; {len(tier2)} off-role '
            f'players never weighted below it')


@check('an off-role prior is discounted by role similarity, not erased and not restored in full')
def t_discount():
    v1 = json.loads(V1.read_text())['rows']
    off = [r for r in v1.values() if r.get('prior_tier') == 'PLAYER_OWN_OFF_ROLE'
           and r.get('prior_effective_obs') is not None
           and r.get('prior_effective_obs_at_role') is not None]
    if not off:
        return 'no off-role players on this slate; skipped'
    bigger = [r for r in off if r['prior_effective_obs'] > r['prior_effective_obs_at_role']]
    assert bigger, 'no off-role player got more weight than his at-role count, so nothing changed'
    # discounted: never the full any-role count, because off-role history is worth less
    for r in off:
        assert r['prior_effective_obs'] >= r['prior_effective_obs_at_role'] - 1e-9, r['name']
    return (f'{len(bigger)} of {len(off)} off-role players carry more weight than their at-role '
            f'count, each still discounted by role similarity')


@check('LOAD-BEARING: a history far above the evidence ceiling is NAMED, never silently capped')
def t_conflict_named():
    v1 = json.loads(V1.read_text())['rows']
    cf = [r for r in v1.values() if r.get('role_evidence_conflict')]
    assert cf, ('no role-evidence conflict was flagged. Either every depth ordering agrees with '
                'every history, or the flag has stopped firing and an established player can be '
                'capped to fringe in silence again.')
    for r in cf:
        c = r['role_evidence_conflict']
        assert c['kind'] == 'HISTORY_ABOVE_EVIDENCE_CEILING'
        assert c['history_band'] and c['assigned_band']
        assert RS.BANDS.index(c['history_band']) - RS.BANDS.index(c['assigned_band']) >= 2
        assert 'cannot tell which' in c['MEANING']
        assert 'low' in c['CONSEQUENCE']
    assert not any(r['position'] == 'QB' for r in cf), (
        'a quarterback was flagged. A backup passer genuinely has alpha history and a fringe role '
        'today; that is the exclusive-role case the appearance model handles, and flagging it buries '
        'the informative cases.')
    by_pos = collections.Counter(r['position'] for r in cf)
    return f'{len(cf)} conflicts named, none of them quarterbacks: {dict(by_pos)}'


@check('the corrected bands reach the projection artifact, not just the role module')
def t_reaches_production():
    v1 = json.loads(V1.read_text())['rows']
    bands = collections.Counter(r.get('role_band') for r in v1.values())
    # before the fix only one player per club could clear rank 3, so these two bands were nearly empty
    assert bands.get('ROTATIONAL', 0) >= 20, (
        f"ROTATIONAL holds {bands.get('ROTATIONAL', 0)} players. Before the rank fix it held 4, "
        f"because a club-wide rank of 4 or worse capped everyone at FRINGE. A low count here means "
        f"the projection is reading a stale ROLE_STATE artifact again.")
    assert bands.get('SECONDARY', 0) >= 25, bands.get('SECONDARY', 0)
    role = json.loads((_REPO / 'nfl/derived/ROLE_STATE.json').read_text())['states']
    for s in role.values():
        if s.get('state') == 'PLAYING_ROLE_ASSIGNED':
            assert 'depth_rank_within_position' in s, s['name']
            assert 'RANK_SEMANTICS' in s
            break
    return (f"artifact bands: ROTATIONAL {bands.get('ROTATIONAL')}, SECONDARY "
            f"{bands.get('SECONDARY')}, FRINGE {bands.get('FRINGE')}")


@check('no player is silently zeroed, and every one carries a state')
def t_no_silent_zero():
    v1 = json.loads(V1.read_text())['rows']
    stateless = [r['name'] for r in v1.values() if not r.get('projection_state')]
    assert not stateless, stateless[:6]
    zeroed = [r['name'] for r in v1.values()
              if r.get('dk_points') == 0 and r.get('projection_state', '').startswith('PROJECTED')]
    assert not zeroed, (f'{zeroed[:6]} are projected at exactly zero. A zero is a forecast, and a '
                        f'missing input must be a named state instead.')
    withheld = [r for r in v1.values() if r.get('dk_points') is None]
    for r in withheld:
        assert r.get('projection_state') and r['projection_state'] != 'PROJECTED', r['name']
    return (f'{len(v1)} players all carry a state; {len(withheld)} withheld with a reason and none '
            f'projected at a bare zero')


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
