"""Frames, history indices, role ranks and the derived constants.

THE FRAME IS THE PART MOST PEOPLE GET WRONG, SO IT IS DECLARED TWICE OVER.

FRAME_A -- "point-in-time eligible". A player is in team T's frame at ordinal o
if he recorded at least one opportunity for T in T's three most recent games
strictly before o (within the season; at a season opener, T's last three games
of the previous season). Membership is therefore a function of prior games
only. A player selected this way who then does not play scores an ACTUAL OF
ZERO and the baseline eats that error, which is the honest accounting: absence
is a forecasting problem, not a sampling inconvenience.

FRAME_B -- "appeared". The same rows restricted to those where the subject
actually recorded an opportunity in the forecast game. THIS CONDITIONS ON THE
OUTCOME and is reported only as a secondary, labelled frame. It answers a
different question -- how well the level is forecast GIVEN that the player
played -- and it is the frame most comparable to the engine's rate layers.

Neither frame knows about trades, releases or the offseason: this package has
no roster feed and does not invent one. The cost is measured
(`frame_a_zero_actual_rate`) rather than assumed away.
"""
from __future__ import annotations

import collections
import statistics

from nfl.research.baselines import estimators as E
from nfl.research.baselines.panel import ordinal

#: Which positions are eligible to carry each quantity, and which quantity
#: orders the depth of that position group.
QUANTITY_POSITIONS = {
    'pass_att': ('QB',), 'pass_cmp': ('QB',), 'pass_yds': ('QB',),
    'pass_td': ('QB',), 'pass_int': ('QB',),
    'carries': ('RB',), 'rush_yds': ('RB',),
    'targets': ('WR', 'TE'), 'receptions': ('WR', 'TE'),
    'rec_yds': ('WR', 'TE'), 'rec_td': ('WR', 'TE'),
}
OPPORTUNITY_OF = {'QB': 'pass_att', 'RB': 'carries', 'WR': 'targets',
                  'TE': 'targets'}
TEAM_QUANTITIES = ('team_plays', 'team_pass_att', 'team_rush_att',
                   'team_dropbacks')

#: The frame window, in the team's own completed games. Three is a declared
#: choice, not a fitted one: it is the shortest window that survives a single
#: inactive game without emptying, and it was NOT selected by score.
FRAME_WINDOW_GAMES = 3

ESTIMATION_SEASONS = (2021, 2022)
EVALUATION_SEASONS = (2023, 2024)


class FrameEmpty(Exception):
    """A frame was built and contains nothing. That is an error, not a result."""


# ------------------------------------------------------------------ index
class Index:
    """Everything derived from the panel that a forecast may lawfully read."""

    def __init__(self, panel):
        self.players = panel['players']
        self.teams = panel['teams']
        self.audit = panel['audit']
        self.identity = panel['identity']
        if not self.players or not self.teams:
            raise FrameEmpty('BASELINE_INDEX_EMPTY_PANEL')

        self.pos = {}
        self.by_key = {}                      # (pid, ordinal) -> row
        self.team_games = collections.defaultdict(list)   # team -> [ordinal]
        self.team_roster = collections.defaultdict(dict)  # (team,ord)->{pid:opp}
        self.series = collections.defaultdict(list)       # (pid,q) -> [(o,v)]
        self.team_series = collections.defaultdict(list)  # (team,q)->[(o,v)]
        self.game_of = {}                     # (team, ordinal) -> game_id

        for r in self.teams:
            o = ordinal(r['season'], r['week'])
            self.team_games[r['team']].append(o)
            self.game_of[(r['team'], o)] = r['game_id']
            for q in TEAM_QUANTITIES:
                self.team_series[(r['team'], q)].append((o, float(r[q])))
        for t in self.team_games:
            self.team_games[t] = sorted(set(self.team_games[t]))
        for k in self.team_series:
            self.team_series[k].sort()

        for r in self.players:
            o = ordinal(r['season'], r['week'])
            self.pos[r['gsis_id']] = r['position']
            self.by_key[(r['gsis_id'], o)] = r
            opp = (r['pass_att'] + r['carries'] + r['targets'])
            if opp >= 1:
                self.team_roster[(r['team'], o)][r['gsis_id']] = opp
            for q in QUANTITY_POSITIONS:
                self.series[(r['gsis_id'], q)].append((o, float(r[q])))
        for k in self.series:
            self.series[k].sort()

    # -------------------------------------------------------------- frame
    def frame_window(self, team: str, o: int):
        """T's last `FRAME_WINDOW_GAMES` completed games before `o`.

        In-season if any exist, otherwise the tail of the previous season --
        which is the season-opener case, and the only place the window touches
        week 18 at all. It is used to decide WHO IS ON THE LIST, never to
        estimate HOW MUCH, and the distinction matters: the 59/160 week-1
        pathology is about levels carried from week 18, not about membership.
        """
        oo = self.team_games.get(team, [])
        prev = [x for x in oo if x < o]
        if not prev:
            return []
        season = o // 100
        same = [x for x in prev if x // 100 == season]
        pool = same if same else [x for x in prev if x // 100 == season - 1]
        return pool[-FRAME_WINDOW_GAMES:]

    def frame_a(self, quantity: str, seasons):
        """Rows `(game_id, team, pid, position, ordinal, actual)`."""
        positions = QUANTITY_POSITIONS[quantity]
        out = []
        for r in self.teams:
            if r['season'] not in seasons:
                continue
            o = ordinal(r['season'], r['week'])
            team = r['team']
            cands = {}
            for w in self.frame_window(team, o):
                for pid, opp in self.team_roster.get((team, w), {}).items():
                    if self.pos.get(pid) in positions:
                        cands[pid] = cands.get(pid, 0.0) + opp
            rank = self.role_rank(team, o, positions)
            for pid in sorted(cands):
                row = self.by_key.get((pid, o))
                actual = float(row[quantity]) if (
                    row is not None and row['team'] == team) else 0.0
                played = 1 if (row is not None and row['team'] == team and
                               (row['pass_att'] + row['carries'] +
                                row['targets']) >= 1) else 0
                out.append(dict(game_id=r['game_id'], team=team, pid=pid,
                                position=self.pos[pid], ordinal=o,
                                season=r['season'], week=r['week'],
                                rank=rank.get(pid, 99),
                                actual=actual, played=played))
        if not out:
            raise FrameEmpty(f'BASELINE_FRAME_A_EMPTY:{quantity}:{seasons}')
        return out

    def team_frame(self, quantity: str, seasons):
        out = []
        for r in self.teams:
            if r['season'] not in seasons:
                continue
            o = ordinal(r['season'], r['week'])
            out.append(dict(game_id=r['game_id'], team=r['team'],
                            pid=r['team'], position='TEAM', ordinal=o,
                            season=r['season'], week=r['week'], rank=1,
                            actual=float(r[quantity]), played=1))
        if not out:
            raise FrameEmpty(f'BASELINE_TEAM_FRAME_EMPTY:{quantity}:{seasons}')
        return out

    # --------------------------------------------------------------- rank
    def role_rank(self, team: str, o: int, position_group) -> dict:
        """pid -> within-team usage rank, from the frame window ONLY.

        Ties are broken by gsis_id so the rank is deterministic; a rank that
        depends on dict order is a silent source of run-to-run difference and
        this project has already found one of those.
        """
        tot = {}
        for w in self.frame_window(team, o):
            for pid, opp in self.team_roster.get((team, w), {}).items():
                if self.pos.get(pid) in position_group:
                    tot[pid] = tot.get(pid, 0.0) + opp
        order = sorted(tot.items(), key=lambda kv: (-kv[1], kv[0]))
        return {pid: i + 1 for i, (pid, _) in enumerate(order)}

    def hist(self, pid: str, quantity: str, o: int):
        if quantity in TEAM_QUANTITIES:
            return E.prior(self.team_series[(pid, quantity)], o)
        return E.prior(self.series[(pid, quantity)], o)


# -------------------------------------------------------------- constants
def variance_components(idx: Index, quantity: str, positions, seasons):
    """(sigma2_within, sigma2_between, k) for one quantity and position group.

    sigma2_within is the pooled within-player-season variance of the per-game
    value; sigma2_between is the variance of player-season means with the
    sampling component sigma2_within / n removed, which is what stops k
    collapsing toward zero purely because short seasons are noisy.
    """
    cells = collections.defaultdict(list)
    for r in idx.players:
        if r['season'] not in seasons or r['position'] not in positions:
            continue
        cells[(r['gsis_id'], r['season'])].append(float(r[quantity]))
    usable = {k: v for k, v in cells.items() if len(v) >= 4}
    if len(usable) < 20:
        raise FrameEmpty(
            f'BASELINE_VARCOMP_TOO_FEW_CELLS:{quantity}:{len(usable)}')
    within, means, ns = [], [], []
    for v in usable.values():
        within.append(statistics.pvariance(v) * len(v) / (len(v) - 1))
        means.append(statistics.mean(v))
        ns.append(len(v))
    s2w = statistics.mean(within)
    nbar = statistics.mean(ns)
    s2m = statistics.pvariance(means) * len(means) / (len(means) - 1)
    s2b = max(s2m - s2w / nbar, 1e-9)
    return s2w, s2b, s2w / s2b


def carryover_slope(idx: Index, quantity: str, positions, y0: int, y1: int):
    """OLS slope of season-`y1` mean on season-`y0` mean. A FIT, to the
    estimation window only, and labelled as a fit wherever it is reported."""
    a, b = {}, {}
    for r in idx.players:
        if r['position'] not in positions:
            continue
        if r['season'] == y0:
            a.setdefault(r['gsis_id'], []).append(float(r[quantity]))
        elif r['season'] == y1:
            b.setdefault(r['gsis_id'], []).append(float(r[quantity]))
    xs, ys = [], []
    for pid in set(a) & set(b):
        if len(a[pid]) >= 4 and len(b[pid]) >= 4:
            xs.append(statistics.mean(a[pid]))
            ys.append(statistics.mean(b[pid]))
    if len(xs) < 20:
        raise FrameEmpty(
            f'BASELINE_CARRYOVER_TOO_FEW_PAIRS:{quantity}:{len(xs)}')
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return (sxy / sxx if sxx > 0 else 0.0), len(xs)


def league_prior_table(idx: Index, quantity: str, before_season: int,
                       frame_rows_by_season):
    """Position -> mean over FRAME_A rows of seasons strictly before
    `before_season`. Computed on the frame population, not on appearances, so
    the prior is the mean of the thing actually being forecast."""
    acc = collections.defaultdict(list)
    for s, rows in frame_rows_by_season.items():
        if s >= before_season:
            continue
        for r in rows:
            acc[r['position']].append(r['actual'])
    out = {p: statistics.mean(v) for p, v in acc.items() if v}
    if not out:
        raise FrameEmpty(f'BASELINE_PRIOR_TABLE_EMPTY:{quantity}')
    return out


def role_table(idx: Index, quantity: str, before_season: int,
               frame_rows_by_season, max_rank: int = 6):
    acc = collections.defaultdict(list)
    for s, rows in frame_rows_by_season.items():
        if s >= before_season:
            continue
        for r in rows:
            acc[(r['position'], min(r['rank'], max_rank))].append(r['actual'])
    means = {k: statistics.mean(v) for k, v in acc.items() if v}
    if not means:
        raise FrameEmpty(f'BASELINE_ROLE_TABLE_EMPTY:{quantity}')
    return {'means': means, 'max_rank': max_rank}
