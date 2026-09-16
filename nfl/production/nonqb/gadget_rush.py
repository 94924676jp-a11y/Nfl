"""The rushing mass that had no player, given to the player who took it.

WHAT WAS UNNAMED. A1 partitions every team carry into exactly one of six
categories, so nothing is lost -- but four of those categories reached the
board as a team-level number with no player on it. Measured on the sealed
DET-BUF run: kneel 1.560 / 0.641, wr 0.478 / 0.584, te 0.058 / 0.040, fringe
0.431 / 0.162, plus the unmodelled-back pool 0.344 / 0.325. That is 2.87 of
Buffalo's 30.08 carries and 1.75 of Detroit's 29.21 -- 9.5% and 6.0% of the
rushing game belonging to nobody.

WHICH OF IT HAS AN OWNER, MEASURED RATHER THAN ASSUMED. Over the pre-cutoff
corpus:

    kneel   2,212 carries, 100.0% taken by a QB, 83.2% by the game's own
            primary passer. Identity exists and is close to certain.
    wr      2,685 carries. The busiest wide receiver in a team-game takes a
            MEDIAN of 100% and a mean of 91.7% of them -- clubs have a gadget
            receiver, not a committee. Identity exists.
    te        203 carries, 99.0% concentrated the same way. Identity exists.
    fringe    132 carries in five seasons: 28 defensive backs, 26 punters, 12
            linebackers, 1 kicker, and 65 from 11 rushers with no position in
            any source we hold. Identity mostly does NOT exist, and where it
            does the player is not on any offensive board. Fringe STAYS
            unnamed, and that is the correct answer rather than a gap.

So three categories are allocated here and the fourth is not. "No unnamed
mass where identity exists" is not "no unnamed mass".

THE MODEL, AND ITS ONE NUMBER. Within a team-game the category's carries are
dealt multinomially over the club's eligible players at that position with
weight `own prior carries in this category + ALPHA`. Alpha is the only free
parameter and it governs how much a player with no history can still take.

ALPHA IS FITTED, AND THE FIRST FIT WAS WRONG. Matching the mean top-share is
MONOTONE in alpha, so it returned the smallest value on the grid every time
-- and alpha = 0 asserts that a player with no prior carry can never take
one, which is false for every rookie and everyone who changed club. That
criterion is withdrawn. Alpha is fitted instead by the mean log-loss of the
ACTUAL owner of each carry under the weights, scored forward on team-games
strictly after the prior that weights them. It is proper, it has an interior
optimum, and it punishes alpha = 0 with an unbounded loss the moment a carry
goes to someone with no history.

    wr   alpha 0.75  mean log-loss 1.2612 over 2,685 carries
    te   alpha 0.10  mean log-loss 0.7411 over   203 carries

Both interior to the grid [0.02, 5.0]. Zero carries went to an owner outside
the club's constructed pool, which is what makes the pool itself credible.
The simulated concentration is slightly UNDER the observed one -- wr 0.873
against 0.917 -- and that is reported rather than tuned away, because moving
alpha to close it is the moment-matching this docstring just withdrew.

KNEELS ARE NOT FITTED AT ALL. Every kneel in the corpus is a QB kneel, and it
goes to the quarterback with the most dropbacks IN THAT DRAW. That is a
structural rule, not an estimated share: in a world where the backup throws
most of the passes, the backup is the one kneeling. It reproduces the 83.2%
primary-passer rate as a consequence rather than as a coefficient.

AND IT MATTERS, WHICH IS WHY IT IS WORTH DOING. A kneel is a rush attempt in
the official stats and it loses a yard or two, so kneels DEPRESS a
quarterback's rushing yards. A board that hides them overstates every
quarterback rushing line on a team that is ahead.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import hashlib
import json
import pathlib
import pickle
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production import derived as DERIVED                        # noqa: E402
from nfl.production import seeds as SEEDS                            # noqa: E402

SPEC_VERSION = 'gadget-rush-allocation-1'
CATEGORIES = ('wr', 'te')

#: Fitted by forward-scored log-loss, NOT by matching a moment. See the module
#: docstring for why the moment-match was withdrawn, and
#: GADGET_RUSH_FIT.json for the full grid.
ALPHA = {'wr': 0.75, 'te': 0.10}

#: The fringe category and the unmodelled-back pool are NOT allocated. Named
#: here so a reader sees the decision rather than the absence of one.
NOT_ALLOCATED = {
    'fringe': 'measured 132 carries pre-cutoff: 28 DB, 26 P, 12 LB, 1 K, and '
              '65 from 11 rushers with no position in any source held. Where '
              'an owner exists he is not on an offensive board.',
    'unmodelled_back_pool': 'by construction the share of the rb category '
                            'dealt to backs OUTSIDE the modelled set. Naming '
                            'it would mean inventing the back.',
}

_CACHE: dict = {}


def fit(cut_ordinal: int) -> Outcome:
    """Per-team, per-player prior carries in each gadget category."""
    key = ('fit', int(cut_ordinal))
    if key in _CACHE:
        return _CACHE[key]
    files = sorted(glob.glob(str(
        _REPO / 'nfl/research/postgame/pbp_20*.csv.gz')))
    if not files:
        return Outcome.blocked(
            'GADGET_PBP_ABSENT',
            'no play-by-play under nfl/research/postgame, so neither the '
            'gadget pools nor their weights can be built.', cause=Cause.DATA)
    ready = DERIVED.artifacts()
    if ready.state is not State.PASS:
        return ready
    p = pathlib.Path(ready.value) / 'panel_enriched.pkl'
    if not p.exists():
        return Outcome.blocked(
            'GADGET_PANEL_ABSENT', f'{p} is not in the verified derived cache',
            cause=Cause.DEPENDENCY)
    with open(p, 'rb') as fh:
        rows = pickle.load(fh)
    pos = {}
    for r in rows:
        g = r.get('gsis_id')
        if g and g not in pos and r.get('position'):
            pos[g] = r['position']
    if not pos:
        return Outcome.blocked(
            'GADGET_POSITIONS_EMPTY',
            'the derived panel yielded no gsis_id -> position map, so every '
            'rusher would be uncategorised and the pools would be empty.',
            cause=Cause.DATA)

    weights = {c: collections.defaultdict(collections.Counter)
               for c in CATEGORIES}
    seen = {c: 0 for c in CATEGORIES}
    for f in files:
        for r in csv.DictReader(gzip.open(f, 'rt')):
            s, w = r.get('season'), r.get('week')
            if not s or not w:
                continue
            try:
                if int(s) * 100 + int(w) >= int(cut_ordinal):
                    continue
            except ValueError:
                continue
            if str(r.get('rush_attempt') or '0') not in ('1', '1.0'):
                continue
            if str(r.get('qb_scramble') or '0') in ('1', '1.0'):
                continue
            if str(r.get('qb_kneel') or '0') in ('1', '1.0'):
                continue
            t = (r.get('posteam') or '').strip()
            rid = (r.get('rusher_player_id') or '').strip()
            if not t or not rid:
                continue
            pp = pos.get(rid)
            c = 'wr' if pp == 'WR' else 'te' if pp == 'TE' else None
            if c is None:
                continue
            weights[c][t][rid] += 1
            seen[c] += 1

    thin = [c for c in CATEGORIES if seen[c] < 50]
    if thin:
        return Outcome.blocked(
            'GADGET_HISTORY_TOO_THIN',
            f'{thin} carry fewer than 50 pre-cutoff carries ({seen}). Weights '
            f'built on that are not a measured allocation.',
            cause=Cause.DATA, counts=seen)

    doc = {'spec_version': SPEC_VERSION, 'cut_ordinal': int(cut_ordinal),
           'alpha': dict(ALPHA), 'positions': pos,
           'weights': {c: {t: dict(v) for t, v in weights[c].items()}
                       for c in CATEGORIES},
           'n_prior_carries': dict(seen),
           'not_allocated': dict(NOT_ALLOCATED),
           'sources': [str(pathlib.Path(f).relative_to(_REPO)) for f in files]}
    out = Outcome.ok('GADGET_FIT_OK', value=doc, spec_version=SPEC_VERSION,
                     n_prior_carries=dict(seen), alpha=dict(ALPHA),
                     cut_ordinal=int(cut_ordinal))
    _CACHE[key] = out
    return out


def pool(doc, team: str, category: str, candidates) -> list:
    """The club's eligible players at the gadget position, as ids.

    `candidates` are the board's own players -- the pool is never wider than
    the participant set the rest of the forecast used. A category carry can
    only go to someone the board already models, which is what stops this
    from quietly introducing a player nobody vetted.
    """
    want = 'WR' if category == 'wr' else 'TE'
    return sorted(g for g in candidates if doc['positions'].get(g) == want)


def allocate(doc, team: str, category: str, counts, candidates, seed,
             tag='') -> Outcome:
    """Deal this category's per-draw carries over the club's named players."""
    ids = pool(doc, team, category, candidates)
    C = np.maximum(np.rint(np.asarray(counts, float)), 0).astype(int)
    if not ids:
        # NOT AN ERROR AND NOT A SILENT ZERO. The club models nobody at this
        # position, so these carries genuinely have no owner on this board and
        # they stay in the category, reported as unallocated.
        return Outcome.not_applicable(
            'GADGET_NO_NAMED_PLAYER_AT_POSITION',
            f'{team} has no modelled {category.upper()} on this board, so its '
            f'{float(C.mean()):.3f} mean {category} carries keep no named '
            f'owner. They remain in the category and are reported as '
            f'unallocated rather than dropped.',
            team=team, category=category,
            mean_unallocated=float(C.mean()))
    w = np.array([doc['weights'][category].get(team, {}).get(g, 0)
                  + ALPHA[category] for g in ids], dtype=float)
    w = w / w.sum()
    # STABLE ACROSS PROCESSES. `hash()` on a tuple of strings is salted per
    # process, so this was not reproducible. seeds.row_component is the
    # declared open-set derivation; the layer's own stream id comes from the
    # readable table beside it.
    _rc = SEEDS.row_component(f'gadget|{team}|{category}|{tag}')
    if _rc.state is not State.PASS:
        return _rc
    _sid = SEEDS.stream_id('gadget_rush', 'category_allocation')
    rng = np.random.default_rng(
        [int(seed), int(_sid.value), int(_rc.value), len(C)])
    out = np.zeros((len(ids), C.shape[0]), dtype=np.int64)
    for j in range(C.shape[0]):
        if C[j] > 0:
            out[:, j] = rng.multinomial(int(C[j]), w)
    # EVERY CARRY IN, EVERY CARRY OUT. The multinomial conserves by
    # construction; this asserts it rather than trusting the construction,
    # because a conservation this file claims is one a reader will rely on.
    bad = int((out.sum(0) != C).sum())
    if bad:
        return Outcome.fail(
            'GADGET_ALLOCATION_DOES_NOT_CONSERVE',
            f'{bad} draw(s) allocate a different number of {category} carries '
            f'than the category held for {team}.', n_draws_bad=bad)
    return Outcome.ok(
        'GADGET_ALLOCATED', value={'row_ids': ids, 'counts': out},
        spec_version=SPEC_VERSION, team=team, category=category,
        n_players=len(ids), alpha=ALPHA[category],
        mean_allocated=float(C.mean()),
        weights={g: round(float(x), 6) for g, x in zip(ids, w)},
        players_with_no_prior_carry=sorted(
            g for g in ids
            if not doc['weights'][category].get(team, {}).get(g)))


def kneels_to_primary_passer(kneel_counts, qb_dropback_draws, qb_ids, seed=0):
    """Every kneel to the quarterback who threw most IN THAT DRAW.

    Not a share and not a fit. The kneeler is the quarterback on the field at
    the end of the game, and the best per-draw evidence for who that is, is
    who took the dropbacks in that same draw. Ties go to the first row, which
    is deterministic rather than arbitrary-looking: a tie means the two are
    indistinguishable on this board's own evidence.
    """
    K = np.maximum(np.rint(np.asarray(kneel_counts, float)), 0).astype(int)
    D = np.asarray(qb_dropback_draws, float)
    if D.shape[0] != len(qb_ids) or D.shape[1] != K.shape[0]:
        return Outcome.fail(
            'KNEEL_DRAW_INDEX_MISMATCH',
            f'dropback draws have shape {D.shape} against {len(qb_ids)} '
            f'quarterback(s) and {K.shape[0]} draw(s).')
    if not len(qb_ids):
        return Outcome.not_applicable(
            'KNEEL_NO_QUARTERBACK_ON_BOARD',
            'this club models no quarterback, so its kneels keep no named '
            'owner and stay in the category.',
            mean_unallocated=float(K.mean()))
    who = D.argmax(axis=0)
    out = np.zeros((len(qb_ids), K.shape[0]), dtype=np.int64)
    out[who, np.arange(K.shape[0])] = K
    bad = int((out.sum(0) != K).sum())
    if bad:
        return Outcome.fail('KNEEL_ALLOCATION_DOES_NOT_CONSERVE',
                            f'{bad} draw(s) do not conserve kneels.')
    return Outcome.ok(
        'KNEELS_ALLOCATED', value={'row_ids': list(qb_ids), 'counts': out},
        spec_version=SPEC_VERSION, n_qbs=len(qb_ids),
        mean_kneels=float(K.mean()),
        rule='per-draw argmax of quarterback dropbacks',
        historical_primary_passer_rate=0.832,
        note='100.0% of 2212 pre-cutoff kneels were taken by a quarterback')
