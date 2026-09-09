"""The D2b production input: prior-only pass-snap share, ewma half-life 2.

The accepted Stage-2 estimator is `ewma_hl2` for WR, TE and RB
(`nfl/research/s2/s2_verdict.json` -> best_method). This module supplies that
quantity for an UPCOMING week, which is the one thing the research code cannot
do: `s2_lib.attach` walks a panel of PLAYED games, and week 1 of 2026 has not
been played.

WHAT IS IMPORTED AND WHAT IS NOT

    s2_lib.ewma            the estimator itself -- imported, never restated
    s2_lib.TARGET, HALFLIVES, POS   the estimand and its constants

The prefix cut is the one piece of bookkeeping here, and it is the piece that
has bitten this project before: a player-ordinal pair can carry TWO rows when a
player changed team mid-week, so "everything appended so far" lets the second
row read the first. `bisect` on strictly-earlier ordinals is what P4E and S2
both use, and it is what is used here.

IT IS AN UPPER BOUND, NOT ROUTES RUN. `s_pass_snaps` counts dropbacks the
player was on the field for; he may have blocked on any of them. The warning
travels with the value.
"""
from __future__ import annotations

import bisect
import collections
import csv
import gzip
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 's2')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

PANEL = _REPO / 'nfl' / 'research' / 'inputs' / 'panel_p3.csv.gz'
SPEC_VERSION = 'participation-s2-ewma_hl2-frozen-1'
HALF_LIFE = 2.0
POSITIONS = ('WR', 'TE', 'RB')
KNOWN_LIMITATION = ('pass_snaps / team_dropbacks_part is an UPPER BOUND on '
                    'route participation, not routes run')

_CACHE: dict = {}


def _ewma():
    """The frozen estimator. Imported so production cannot drift from it."""
    import s2_lib as S
    if abs(S.HALFLIVES[0] - HALF_LIFE) > 1e-12:
        raise AssertionError(
            f'S2 half-life set moved: {S.HALFLIVES}. The accepted estimator '
            f'is ewma_hl{HALF_LIFE:g} and production will not silently follow '
            f'a different one.')
    return S.ewma


def _history(ordinal_cut: int):
    """Per-player list of (ord, s_pass_snaps) for APPEARED player-games."""
    key = ('hist', ordinal_cut)
    if key in _CACHE:
        return _CACHE[key]
    hist = collections.defaultdict(list)
    ords = collections.defaultdict(list)
    pos_sum, pos_n = collections.Counter(), collections.Counter()
    rows = []
    with gzip.open(PANEL, 'rt') as fh:
        for r in csv.DictReader(fh):
            if r.get('position') not in POSITIONS:
                continue
            o = int(r['season']) * 100 + int(r['week'])
            if o >= ordinal_cut:
                continue
            den = float(r.get('team_dropbacks_part') or 0)
            snaps = float(r.get('pass_snaps') or 0)
            pct = r.get('offense_pct')
            appeared = bool(pct not in (None, '', '0', '0.0'))
            if den <= 0 or not appeared:
                continue
            rows.append((o, r['gsis_id'], r['position'], snaps / den))
    rows.sort()
    for o, pid, pos, v in rows:
        hist[pid].append(v)
        ords[pid].append(o)
        pos_sum[pos] += v
        pos_n[pos] += 1
    pos_mean = {p: (pos_sum[p] / pos_n[p]) if pos_n[p] else None
                for p in POSITIONS}
    _CACHE[key] = (hist, ords, pos_mean, len(rows))
    return _CACHE[key]


def cache_clear():
    _CACHE.clear()


def share_prior(season: int, week: int, players) -> Outcome:
    """ewma_hl2 of prior appeared pass-snap shares, per player."""
    cut = season * 100 + week
    ew = _ewma()
    hist, ords, pos_mean, n_rows = _history(cut)
    if not n_rows:
        return Outcome.blocked(
            'PARTICIPATION_HISTORY_EMPTY',
            f'no player-game earlier than {season} week {week} carries a '
            f'pass-snap share; an estimator fitted on nothing is not the '
            f'accepted estimator', cause=Cause.DATA)
    out, fell_back, unknown = {}, [], []
    for q in players:
        pid, pos = q.get('gsis_id'), q.get('position')
        if pos not in POSITIONS:
            continue
        if not pid:
            unknown.append(q.get('player_name'))
            continue
        k = bisect.bisect_left(ords[pid], cut)      # STRICTLY earlier only
        vals = hist[pid][:k]
        v = ew(vals, HALF_LIFE) if vals else None
        if v is None:
            # The DECLARED fallback, matching s2_lib.predict: the positional
            # mean, never a silent zero. A player with no history is a real
            # case (rookies, week 1) and it is named in the evidence.
            v = pos_mean.get(pos)
            fell_back.append(pid)
        if v is None:
            return Outcome.fail(
                'PARTICIPATION_PRIOR_UNAVAILABLE',
                f'neither a player history nor a positional mean exists for '
                f'{pos}; no value is invented')
        out[pid] = float(min(max(v, 0.0), 1.0))
    if unknown:
        return Outcome.fail(
            'PARTICIPATION_IDENTITY_UNRESOLVED',
            f'{len(unknown)} player(s) carry no gsis_id; fuzzy name matching '
            f'is forbidden', n=len(unknown))
    if not out:
        return Outcome.fail(
            'PARTICIPATION_PRIOR_EMPTY',
            f'no WR/TE/RB among {len(players)} player(s), so the prior covers '
            f'nobody. An empty prior is not a prior.')
    return Outcome.ok(
        'PARTICIPATION_PRIOR_OK', value=out, spec_version=SPEC_VERSION,
        estimator=f'ewma_hl{HALF_LIFE:g}', n_players=len(out),
        n_history_rows=n_rows, ordinal_cut=cut,
        n_on_positional_mean=len(fell_back),
        positional_mean={k: (round(v, 6) if v is not None else None)
                         for k, v in pos_mean.items()},
        warnings=[f'known limitation: {KNOWN_LIMITATION}'])
