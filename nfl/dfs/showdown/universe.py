"""The frozen DET @ BUF Showdown universe: draws, salaries, ids, tags.

ONE LOADER, SO EVERY MODULE BELOW IS LOOKING AT THE SAME SLATE. The 2026-09-17
portfolio was built by a script that joined DK salaries to model names inline
and then threw the join away, so nothing afterwards could check what had been
matched to what. This module is the join, it is the only join, and it refuses
rather than guessing.

NOTHING HERE READS A LIVE GAME. The draws are the sealed pregame board and the
salaries are the pre-lock DK file. See LIVE_BARRIER.json.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.showdown import kicker_identity as KI
from nfl.production.dfs import projection_confidence as PC           # noqa: E402

SPEC_VERSION = 'nfl-showdown-universe-1'

# THE SLATE IS AN ARGUMENT, NOT A CONSTANT.
#
# Three postgame graders import this module, so a module-level pin here binds
# all of them: `grade_projections`, `grade_props` and `grade_portfolios` could
# only ever have run DET@BUF, whatever game they were handed. DEF-062.
#
# The pins were not only paths. `OFFICIAL_INACTIVE` is who was ruled out on
# 2026-09-17 and `ROLE_CONCERN` is a Buffalo roster -- one game's football
# baked into a module three graders depend on. Those travel with the slate.
#
# SALARY_CAP, N_FLEX and CPT_MULTIPLIER do NOT: they are DraftKings Showdown
# rules and they are the same for every game. Parameterising them would be
# inventing a knob that models nothing.
DEFAULT_GAME_ID = '2026_02_DET_BUF'
DEFAULT_FROZEN = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/frozen'
SLATE_ENV = 'NFL_SHOWDOWN_SLATE'
SALARY_CAP = 50000
N_FLEX = 5
CPT_MULTIPLIER = 1.5

#: Officially inactive on 2026-09-17. Blocked, not capped.
#: SLATE DATA. Kept as the default slate's value; a different game carries
#: its own, and an empty tuple is a legitimate value (nobody ruled out).
OFFICIAL_INACTIVE = ('Skyler Bell', 'Ty Johnson')

#: Buffalo non-quarterback skill players. CS1 is quarterback-only, so none of
#: these carries current-season role state, and the P2 diagnostic found an
#: appearance inversion on this roster. The tag is a statement about the MODEL,
#: never about the player.
#: SLATE DATA, and the name says so: this is a Buffalo roster.
BUF_ROLE_CONCERN = (
    'James Cook', 'Ray Davis', 'Frank Gore Jr.', 'DJ Moore', 'Khalil Shakir',
    'Keon Coleman', 'Dalton Kincaid', 'Dawson Knox', 'Josh Palmer',
    'Greg Dortch', 'Jackson Hawes', 'Keleki Latu')


#: DECLARED aliases, DK spelling -> board spelling. One entry, one reason.
#: Fuzzy matching is refused: it is how a wrong man gets written into a lineup.
ALIASES = {'joshuapalmer': 'joshpalmer'}

#: KICKERS ARE DELIBERATELY LEFT UNRESOLVED. The sealed board's kicking layer
#: carries TEAM rows, not named players, so a kicker can only be matched by
#: (team, position). That join was already refused once on this fixture and it
#: is refused here for the same reason: it is an inference about a join, not an
#: identity. The consequence is on the record -- the 2026-09-17 portfolio
#: rostered Tyler Bass and Jake Bates at 22.5% each, and the model cannot name
#: either of them.
#: SUPERSEDED 2026-09-18, and kept because the reasoning was wrong in a way
#: worth keeping visible. The kicking layer was never team-keyed: its
#: `row_ids` are gsis_ids (`00-0036162` Tyler Bass, `00-0039172` Jake Bates,
#: both confirmed against the nflverse ids in the postgame capture) and
#: `row_teams` is a descriptive column beside the key. What was missing was a
#: NAME -- `frozen_board_names.json` published 29 offensive ids and omitted
#: these two -- so every name join failed and (team, position) was the only
#: thing left to fall back on. `kicker_identity.resolve` closes it by id.
KICKER_JOIN_REFUSED = ('the kicking layer is team-keyed; resolving a kicker '
                       'would require a (team, position) join')
KICKER_JOIN_REFUSED_SUPERSEDED_BY = 'nfl.dfs.showdown.kicker_identity.resolve'


class Slate:
    """One game's inputs. Immutable, and it never guesses a missing half."""

    __slots__ = ('game_id', 'frozen', 'official_inactive', 'role_concern')

    def __init__(self, game_id, frozen, official_inactive, role_concern):
        self.game_id = game_id
        self.frozen = pathlib.Path(frozen)
        self.official_inactive = tuple(official_inactive)
        self.role_concern = tuple(role_concern)

    def __repr__(self):
        return (f'Slate({self.game_id!r}, {str(self.frozen)!r}, '
                f'{len(self.official_inactive)} inactive, '
                f'{len(self.role_concern)} role-concern)')


def slate(game_id=None, frozen=None, official_inactive=None,
          role_concern=None) -> Slate:
    """Build a slate. A game id does NOT imply a directory.

    Handing back the default frozen directory for an unknown game id is how a
    module reads one game's draws and labels them another's -- the same trap
    `postgame.outcome.slate` refuses. So: both halves, or neither.

    The inactive and role-concern lists default to the DEFAULT slate's only
    when the frozen directory is also the default one. For any other game they
    default to EMPTY, because this module does not know who was ruled out in a
    game it has never seen, and silently reusing 2026-09-17's Buffalo lists
    would tag the wrong players in the wrong game.
    """
    gid = game_id or DEFAULT_GAME_ID
    if frozen is None:
        if game_id and game_id != DEFAULT_GAME_ID:
            raise ValueError(
                f'no frozen directory is known for {game_id!r}. Pass one. '
                f'Guessing it would read {DEFAULT_GAME_ID} and call it '
                f'{game_id}.')
        frozen = DEFAULT_FROZEN
    is_default = pathlib.Path(frozen) == DEFAULT_FROZEN
    if official_inactive is None:
        official_inactive = OFFICIAL_INACTIVE if is_default else ()
    if role_concern is None:
        role_concern = BUF_ROLE_CONCERN if is_default else ()
    return Slate(gid, frozen, official_inactive, role_concern)


_DEFAULT = slate()

#: Back-compatible module names. They ARE the default slate's values, so a
#: reader of either sees one thing, not two that can drift.
FROZEN = _DEFAULT.frozen
GAME_ID = _DEFAULT.game_id


def norm(s: str) -> str:
    s = re.sub(r'\s*\(\d+\)\s*$', '', (s or '').strip())
    s = re.sub(r'\s+(Jr\.|Sr\.|II|III|IV)$', '', s)
    k = re.sub(r'[^a-z]', '', s.lower())
    return ALIASES.get(k, k)


def _tag(name: str, sl: Slate = None) -> str:
    sl = sl or _DEFAULT
    n = norm(name)
    if n in {norm(x) for x in sl.official_inactive}:
        return PC.KNOWN_INACTIVE_STALE
    if n in {norm(x) for x in sl.role_concern}:
        return PC.ROLE_STATE_CONCERN
    return PC.MODEL_SUPPORTED


#: Public alias. The postgame prop grader needs the same tag the DFS
#: universe assigns, and re-deriving it there would be a second copy of
#: the BUF role-concern list that could drift from this one.
confidence_tag = _tag


def load(sl: Slate = None) -> Outcome:
    """(players, dk draws) for the given slate, or a refusal."""
    sl = sl or _DEFAULT
    FROZEN = sl.frozen
    zp = FROZEN / 'sealed_player_draws.npz'
    mp = FROZEN / 'sealed_player_draws_manifest.json'
    sp = FROZEN / 'DKSalaries_showdown.csv'
    for p in (zp, mp, sp):
        if not p.exists():
            return Outcome.blocked(
                'SHOWDOWN_FROZEN_INPUT_MISSING', f'{p} is absent',
                cause=Cause.DATA)
    z = np.load(zp)
    man = json.loads(mp.read_text())
    board_names = {}
    # gsis_id -> name, taken from the layer row ids plus the board's own names
    bj = FROZEN.parent / 'frozen_board_names.json'
    if bj.exists():
        board_names = json.loads(bj.read_text())
    ids = man['layers']['dk_scoring']['row_ids']
    teams = man['layers']['dk_scoring'].get('row_teams') or [None] * len(ids)
    dk = np.asarray(z['dk_scoring__dk_points'], dtype=np.float64)
    if dk.shape[0] != len(ids):
        return Outcome.fail(
            'SHOWDOWN_DRAW_ROW_MISMATCH',
            f'{dk.shape[0]} draw row(s) against {len(ids)} manifest id(s)',
            cause=Cause.DATA)
    by_norm = {}
    for i, g in enumerate(ids):
        nm = board_names.get(g)
        by_norm.setdefault(norm(nm) if nm else None, []).append((i, g, nm))
    # DK salary rows
    rows = []
    for r in csv.reader(sp.read_text().splitlines()):
        if len(r) > 19 and r[11] in ('RB', 'QB', 'WR', 'TE', 'K', 'DST'):
            rows.append({'pos': r[11], 'name': r[13].strip(), 'dk_id': r[14],
                         'slot': r[15], 'salary': int(r[16]),
                         'team': r[18]})
    if not rows:
        return Outcome.fail('SHOWDOWN_SALARY_FILE_EMPTY', str(sp),
                            cause=Cause.DATA)
    return Outcome.ok(
        'SHOWDOWN_UNIVERSE_RAW', value={'dk': dk, 'ids': ids, 'teams': teams,
                                        'salary_rows': rows, 'manifest': man},
        detail=f'{dk.shape[0]} modelled player(s), {dk.shape[1]} draw(s), '
               f'{len(rows)} DK salary row(s)',
        spec_version=SPEC_VERSION, n_draws=int(dk.shape[1]))


def build(sl: Slate = None) -> Outcome:
    """The joined slate. A DK row the model cannot name is IDENTITY_UNRESOLVED,
    never dropped quietly and never matched by position and team."""
    sl = sl or _DEFAULT
    FROZEN = sl.frozen
    raw = load(sl)
    if raw.state is not State.PASS:
        return raw
    v = raw.value
    dk, ids = v['dk'], v['ids']
    # A MISSING BOARD-NAMES FILE IS A REFUSAL, NOT A TRACEBACK.
    # `load` above already guards this file; `build` read it unconditionally
    # and raised FileNotFoundError, which is the one shape this codebase is
    # trying to stop producing -- a stage that fails without saying what it
    # needed. Found by the second-slate fixture, which is what a second
    # fixture is for.
    bj = FROZEN.parent / 'frozen_board_names.json'
    if not bj.exists():
        return Outcome.blocked(
            'SHOWDOWN_BOARD_NAMES_MISSING',
            f'{bj} is absent, so no draw row can be given a name and every '
            f'DK row would come back IDENTITY_UNRESOLVED',
            cause=Cause.DATA)
    names = json.loads(bj.read_text())
    idx = {}
    for i, g in enumerate(ids):
        n = norm(names.get(g, ''))
        if not n:
            continue
        idx.setdefault(n, []).append(i)
    ambiguous = sorted(n for n, rows in idx.items() if len(rows) > 1)
    if ambiguous:
        return Outcome.fail(
            'SHOWDOWN_AMBIGUOUS_MODEL_NAME',
            f'{ambiguous} resolve to more than one draw row. Two players who '
            f'could both be one name is exactly where a fuzzy match writes the '
            f'wrong man into a lineup.', cause=Cause.DATA)
    # KICKERS, BY PLAYER ID. Their draws live in their own layer with its own
    # array, so they carry `kick_draws` rather than a `dk_scoring` row index.
    # Identity comes from `kicker_identity`, which matches on gsis_id and
    # refuses a (team, position) join.
    kick_draws, kick_meta = {}, {}
    ki = KI.resolve(frozen=FROZEN)
    if ki.state is State.PASS:
        z2 = np.load(FROZEN / 'sealed_player_draws.npz')
        if 'kicking__dk_points' in z2.files:
            kd = np.asarray(z2['kicking__dk_points'], dtype=np.float64)
            for gid, r in ki.value.items():
                if r['row'] < kd.shape[0]:
                    kick_draws[norm(r['name'])] = kd[r['row']]
                    kick_meta[norm(r['name'])] = {**r, 'gsis_id': gid}
    players, unresolved = [], []
    for r in v['salary_rows']:
        n = norm(r['name'])
        row = idx.get(n)
        tag = _tag(r['name'], sl)
        if r['pos'] == 'DST':
            tag = PC.UNSUPPORTED
        elif row is None and n not in kick_draws:
            tag = PC.IDENTITY_UNRESOLVED
            unresolved.append(r['name'])
        players.append({
            'dk_id': r['dk_id'], 'name': r['name'], 'pos': r['pos'],
            'team': r['team'], 'slot': r['slot'], 'salary': r['salary'],
            'draw_row': (row[0] if row else None), 'tag': tag,
            'key': n,
            'kicking_layer': n in kick_draws,
            'gsis_id': (kick_meta[n]['gsis_id'] if n in kick_meta else None)})
    flex = [p for p in players if p['slot'] == 'FLEX']
    cpt = {p['key']: p for p in players if p['slot'] == 'CPT'}
    playable = [p for p in flex
                if (p['draw_row'] is not None or p['kicking_layer'])
                and not PC.POLICY[p['tag']]['blocked']
                and p['key'] in cpt]
    for p in playable:
        p['cpt_salary'] = cpt[p['key']]['salary']
        p['cpt_dk_id'] = cpt[p['key']]['dk_id']
        p['draws'] = (kick_draws[p['key']] if p['kicking_layer']
                      else dk[p['draw_row']])
    if not playable:
        return Outcome.fail('SHOWDOWN_NO_PLAYABLE_PLAYERS',
                            'every DK row was blocked or unresolved',
                            cause=Cause.DATA)
    n_draws = int(dk.shape[1])
    tagcount = {}
    for p in players:
        tagcount[p['tag']] = tagcount.get(p['tag'], 0) + 1
    return Outcome.ok(
        'SHOWDOWN_UNIVERSE', value={'players': players, 'playable': playable,
                                    'n_draws': n_draws},
        detail=f'{len(playable)} playable of {len(flex)} DK FLEX row(s); '
               f'{len(unresolved)} identity-unresolved; {n_draws} draws',
        spec_version=SPEC_VERSION, game_id=sl.game_id,
        salary_cap=SALARY_CAP,
        n_playable=len(playable), n_draws=n_draws,
        identity_unresolved=sorted(set(unresolved)),
        tag_counts=tagcount,
        kickers_resolved=sorted(kick_meta),
        kicker_identity_state=f'{ki.state.value}[{ki.code}]',
        kickers_resolved_by='gsis_id, never (team, position)',
        uses_live_game_outcome_data=False)
