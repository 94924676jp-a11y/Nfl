#!/usr/bin/env python3.12
"""Guards every future projection version must pass. V0 is the fixture that proves they fire.

WHY THESE EXIST. On 2026-09-27 the first proprietary projection board (V0, commit
89c919d) reached the owner as a table of deltas against FantasyCruncher before anybody
checked its level. Its slate mean was 61% of the external baseline -- broken arithmetic
presented as a football opinion. Four structural defects caused it, and every one of them
was visible from the specification alone, without any data.

So each guard below detects one of those defects on ANY projection artifact, and the test
file asserts that each one FIRES on V0. A guard that cannot demonstrate a catch on a known
bad board is not a guard, it is a hope. V0 is kept permanently for exactly this reason: it
is the only bad board we have, and deleting it would leave these guards unproven.

The order matters. `assert_level_within_band` runs FIRST in `run_all`, because it is the
one-line check that would have caught all four defects at once and it was the one I
skipped.
"""
from __future__ import annotations

import collections
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402

SPEC_VERSION = 'projection-guards-1'

#: A projection board whose slate mean falls outside this band of an external commercial
#: baseline is refused. NOT a tuning target -- a band this wide cannot make us agree with
#: anyone, but it does catch arithmetic that is broken by tens of percent. Declared.
LEVEL_BAND = (0.85, 1.15)

#: A demonstrated role. A player at or above this observed share has established that he
#: holds a real job, and a correct prior must not shrink him downward.
ESTABLISHED_SHARE = 0.18

#: Volume at which a zero touchdown expectation is indefensible.
REAL_VOLUME = 10.0

#: Output above which a non-starter is being treated as a starter.
STARTER_LEVEL_POINTS = 5.0

ROSTERABLE = ('QB', 'RB', 'WR', 'TE', 'DST')


def _mean(rec):
    m = rec.get('mean')
    return m if isinstance(m, (int, float)) else None


def assert_level_within_band(records, external, salaries=None, band=LEVEL_BAND):
    """DEFECT-0. The one-line check that would have caught everything else.

    EVALUATED ON SLICES, AND HERE IS WHY -- THIS GUARD'S FIRST VERSION HAD THE SAME BUG AS
    THE MODEL IT EXISTS TO CATCH. A flat mean over every joined player put V0 at a ratio of
    0.901, comfortably inside the band, and the guard PASSED a board I had already told the
    owner was 39% low. The flat mean is diluted by ~80 low-salary players where both boards
    project two or three points and agree closely. Averaging over non-contributors hid the
    defect -- exactly what shrinking toward a population mean did to Chase.

    Measured on V0:

        all 223 joined players        ratio 0.901   <- the flat mean, hides it
        salary >= $4500               ratio 0.791
        top 100 by external proj      ratio 0.739
        the players in the 48 lineups ratio 0.61

    The error is concentrated where lineups actually live. So the level is checked on
    several slices and the guard fails if ANY of them is out of band, with the flat ratio
    reported alongside for contrast rather than used as the verdict.
    """
    pairs = [(_mean(r), external.get(k), (salaries or {}).get(k))
             for k, r in records.items()
             if _mean(r) is not None and external.get(k) is not None]
    if len(pairs) < 30:
        return Outcome.not_applicable(
            'LEVEL_BAND_SAMPLE_TOO_SMALL',
            f'only {len(pairs)} players have both a projection and an external baseline; '
            f'a level check on this few would be noise')

    def _ratio(sel):
        if len(sel) < 20:
            return None
        o = statistics.fmean([a for a, _, _ in sel])
        e = statistics.fmean([b for _, b, _ in sel])
        return (round(o / e, 4), round(o, 2), round(e, 2), len(sel)) if e else None

    by_ext = sorted(pairs, key=lambda t: -(t[1] or 0))
    slices = {'all_joined': _ratio(pairs),
              'top_100_by_external': _ratio(by_ext[:100]),
              'top_50_by_external': _ratio(by_ext[:50])}
    if any(t[2] for t in pairs):
        for cut in (4000, 4500):
            slices[f'salary_ge_{cut}'] = _ratio([t for t in pairs
                                                 if (t[2] or 0) >= cut])
    slices = {k: v for k, v in slices.items() if v}
    lo, hi = band
    out = [{'slice': k, 'ratio': v[0], 'ours_mean': v[1], 'external_mean': v[2], 'n': v[3],
            'in_band': lo <= v[0] <= hi} for k, v in slices.items()]
    breached = [r for r in out if not r['in_band']]
    if breached:
        worst = min(breached, key=lambda r: r['ratio'])
        return Outcome.fail(
            'PROJECTION_LEVEL_OUT_OF_BAND',
            f'{len(breached)} of {len(out)} slices fall outside the declared band '
            f'{lo}-{hi}. Worst: {worst["slice"]} at ratio {worst["ratio"]} '
            f'(ours {worst["ours_mean"]} vs external {worst["external_mean"]} over '
            f'{worst["n"]} players). The flat all-players ratio is '
            f'{slices["all_joined"][0]} and would have hidden this -- read the slices.',
            slices=out, worst=worst, band=list(band),
            flat_ratio=slices['all_joined'][0])
    return Outcome.ok('PROJECTION_LEVEL_IN_BAND', out,
                      f'{len(out)} slices all within {lo}-{hi}', slices=out)


def assert_established_role_not_shrunk_down(records):
    """DEFECT-1. A player with a demonstrated large role must not be shrunk downward.

    The V0 bug: shrinkage pulled toward the mean of ALL players at a position, a population
    where 40 of 96 wide receivers held under a 5% target share. The prior was therefore
    0.105 when the mean among role-holders was 0.211, and every genuine starter took a
    24-29% haircut. A correct prior -- the player's own multi-season baseline -- would move
    a quiet two-game sample UP toward what he has repeatedly been, not down toward a
    population of reserves.
    """
    bad = []
    for k, r in records.items():
        opp = r.get('opportunity') or {}
        for obs_f, use_f, what in (('observed_target_share', 'target_share_used', 'target'),
                                   ('observed_carry_share', 'carry_share_used', 'carry')):
            obs, use = opp.get(obs_f), opp.get(use_f)
            if not isinstance(obs, (int, float)) or not isinstance(use, (int, float)):
                continue
            inherited = opp.get(f'inherited_{what}_share') or 0.0
            if obs >= ESTABLISHED_SHARE and (use - inherited) < obs:
                bad.append({'player': r.get('player'), 'position': r.get('position'),
                            'measure': what, 'observed': round(obs, 4),
                            'used': round(use, 4),
                            'haircut_pct': round(100 * (use / obs - 1), 1)})
    if bad:
        worst = sorted(bad, key=lambda x: x['haircut_pct'])[:10]
        return Outcome.fail(
            'ESTABLISHED_ROLE_SHRUNK_TOWARD_POPULATION_MEAN',
            f'{len(bad)} case(s) where a player with an observed share at or above '
            f'{ESTABLISHED_SHARE} was projected on a SMALLER share than he actually held. '
            f'That is the signature of shrinking toward a population mean that includes '
            f'reserves. Shrink toward the player, not the position.',
            violations=worst, n_violations=len(bad))
    return Outcome.ok('ESTABLISHED_ROLE_PRESERVED', len(records),
                      'no established role was projected below its observed share')


def assert_td_rate_not_raw_count(records):
    """DEFECT-2. A zero two-game red-zone count is not a zero touchdown rate.

    The V0 bug: Tee Higgins recorded 26 observed targets and no red-zone looks in the same
    two games, so the model gave him EXACTLY 0.000 expected touchdowns. A receiver with a
    quarter of his team's targets scores touchdowns. Touchdown expectation must come from a
    shrunk RATE with a positional floor, never from a raw count over a two-game window.
    """
    bad = []
    for k, r in records.items():
        sc = r.get('scoring') or {}
        opp = r.get('opportunity') or {}
        td = sc.get('proj_td')
        if not isinstance(td, (int, float)):
            continue
        vol = max(float(opp.get('proj_targets') or 0),
                  float(opp.get('proj_carries') or 0))
        obs = r.get('observed_volume_for_guard')
        if obs is None:
            obs = vol * 2.0  # two games of the projected per-game rate
        if td <= 0.0 and obs >= REAL_VOLUME:
            bad.append({'player': r.get('player'), 'position': r.get('position'),
                        'proj_td': td, 'approx_observed_volume': round(obs, 1)})
    if bad:
        return Outcome.fail(
            'ZERO_TD_EXPECTATION_ON_REAL_VOLUME',
            f'{len(bad)} player(s) with real opportunity volume carry a touchdown '
            f'expectation of zero. A zero count over two games is not a zero rate.',
            violations=bad[:10], n_violations=len(bad))
    return Outcome.ok('TD_RATE_HAS_A_FLOOR', len(records),
                      'no player with real volume carries a zero touchdown expectation')


def assert_no_stale_replacement_role(records, players, predicted_starters):
    """DEFECT-3. An injury-replacement workload must expire when the starter returns.

    The V0 bug: Drew Lock held 95% of Seattle's snaps because Sam Darnold was injured.
    Darnold is reported available again, and V0 still projected Lock at 17.88 points --
    starter output for a player who is not the starter. Observed usage must be read through
    CURRENT role state, not carried forward on its own.
    """
    bad = []
    for k, r in records.items():
        m = _mean(r)
        pos, club = r.get('position'), r.get('team')
        if m is None or pos not in ('QB', 'RB', 'WR', 'TE') or m < STARTER_LEVEL_POINTS:
            continue
        if (r.get('player'), club) in predicted_starters:
            continue
        starter_available = any(
            (nm, cl) in predicted_starters and cl == club
            and players.get(i, {}).get('position') == pos
            for i, v in players.items()
            for nm, cl in ((v['name'], v['team']),))
        if starter_available:
            bad.append({'player': r.get('player'), 'position': pos, 'club': club,
                        'projected_points': m,
                        'why': ('outside the predicted starting group at a position whose '
                                'predicted starter is available, yet projected at '
                                'starter level')})
    if bad:
        return Outcome.fail(
            'STALE_REPLACEMENT_ROLE_RETAINED',
            f'{len(bad)} non-starter(s) projected at or above {STARTER_LEVEL_POINTS} '
            f'points while the predicted starter at their position is available. Current '
            f'role state is not being consumed by the projection.',
            violations=sorted(bad, key=lambda x: -x['projected_points'])[:10],
            n_violations=len(bad))
    return Outcome.ok('ROLE_STATE_CONSUMED', len(records),
                      'no non-starter carries starter-level output behind an available '
                      'starter')


def assert_positional_coverage(records, players, required=ROSTERABLE):
    """DEFECT-4. No rosterable position may have zero proprietary coverage.

    DST had no projection component at all -- the position most likely to be silently
    forgotten, because it has no player-level features whose absence anybody would notice.
    """
    have = collections.Counter()
    for k, r in records.items():
        if _mean(r) is not None:
            have[r.get('position')] += 1
    present = {v['position'] for v in players.values()}
    missing = [p for p in required if p in present and have[p] == 0]
    if missing:
        return Outcome.fail(
            'POSITION_HAS_NO_PROPRIETARY_COVERAGE',
            f'{missing} are rosterable on this slate and carry zero proprietary '
            f'projections. A position with no component is a hole in the product, not a '
            f'slate property.',
            missing=missing, counts=dict(have))
    return Outcome.ok('ALL_POSITIONS_COVERED', dict(have),
                      f'every rosterable position has proprietary coverage: {dict(have)}')


def assert_cold_start_identity_resolved(records, players, conflicts):
    """DEFECT-5. A player with an unresolved identity must not receive a projection.

    Malik McClain: no observed 2026 row, and the research named "Matthew McClain" while the
    DK universe carries Malik. Projecting an unresolved identity assigns football to a name
    we have not established.
    """
    unresolved = set()
    for c in conflicts:
        if c.get('status', '').startswith('OPEN'):
            for i, v in players.items():
                if v['name'].split()[-1] in str(c.get('resolution', '')):
                    unresolved.add(i)
    bad = [{'player': records[i].get('player'), 'mean': _mean(records[i])}
           for i in unresolved if i in records and _mean(records[i]) is not None]
    if bad:
        return Outcome.fail(
            'PROJECTION_ON_UNRESOLVED_IDENTITY',
            f'{len(bad)} player(s) with an OPEN identity conflict carry a projection',
            violations=bad, n_violations=len(bad))
    return Outcome.ok('IDENTITY_RESOLVED_BEFORE_PROJECTION', len(unresolved),
                      f'{len(unresolved)} unresolved identity/identities, none projected')


def assert_concentration_classified(audit, threshold=40.0):
    """DEFECT-6. Heavy portfolio exposure must be classified, not left as a percentage.

    Watson reached 54.2% of lineups. The percentage alone says nothing; what mattered was
    that his FC value of 4.55 points per $1k was the highest on the slate while his only
    independent football support was a snap share every starting quarterback has. Every
    player above the threshold must carry a verdict and its enumerated supports.
    """
    exp = (audit.get('exposure') or {}).get('player_exposure') or {}
    verdicts = {c['player']: c for c in (audit.get('concentration_verdicts') or ())}
    heavy = [n for n, e in exp.items() if e.get('pct', 0) >= threshold]
    missing = [n for n in heavy if n not in verdicts
               or not verdicts[n].get('verdict')
               or verdicts[n].get('independent_football_support') is None]
    if missing:
        return Outcome.fail(
            'CONCENTRATION_NOT_CLASSIFIED',
            f'{len(missing)} player(s) above {threshold}% exposure carry no verdict with '
            f'enumerated football support: {missing}',
            missing=missing, n=len(missing))
    return Outcome.ok('CONCENTRATION_CLASSIFIED', len(heavy),
                      f'{len(heavy)} players above {threshold}% exposure, each with a '
                      f'verdict and its supports')


def run_all(records, players, external, predicted_starters, conflicts, audit=None):
    """Every guard, level check first. Returns {name: Outcome}."""
    out = {
        'level_within_band': assert_level_within_band(
            records, external,
            salaries={k: v.get('salary') for k, v in players.items()}),
        'established_role_not_shrunk_down':
            assert_established_role_not_shrunk_down(records),
        'td_rate_not_raw_count': assert_td_rate_not_raw_count(records),
        'no_stale_replacement_role':
            assert_no_stale_replacement_role(records, players, predicted_starters),
        'positional_coverage': assert_positional_coverage(records, players),
        'cold_start_identity_resolved':
            assert_cold_start_identity_resolved(records, players, conflicts),
    }
    if audit is not None:
        out['concentration_classified'] = assert_concentration_classified(audit)
    return out
