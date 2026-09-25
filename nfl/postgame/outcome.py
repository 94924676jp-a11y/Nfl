"""The outcome artifact: what actually happened, kept apart from what was predicted.

TWO SEPARATIONS THIS FILE EXISTS TO HOLD

  PREGAME_FROZEN_ARTIFACT      the sealed board, the salary file, the market
                               snapshot, the two portfolios. Immutable.
  POSTGAME_OUTCOME             the result. Written once, never merged into the
                               pregame directory.

and

  POSTGAME_MEASUREMENT         grading the frozen board against the result.
  FUTURE_MODEL_DEVELOPMENT     anything that changes the model.

A result may inform the second only through a pre-registration written after
the first is frozen. One slate cannot fit a threshold, an exposure cap or an
architectural reversal, and nothing here is allowed to write into
`nfl/research/dfs/DET_BUF_2026W2/frozen/`.

THE GATE

Every grader in this package calls `require()`. Without a verified outcome
artifact it refuses -- it does not grade against a partial box score, and it
does not accept a final score relayed in conversation. On 2026-09-18 the only
outcome evidence available was the sentence "a high-scoring 41-31 game", which
does not say which side scored 41 and cannot grade a single player stat.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC              # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State     # noqa: E402

import json as _json
import os as _os
import pathlib as _pl

SPEC_VERSION = 'nfl-postgame-outcome-1'

#: The slate this module graded before it could grade any other one.
#:
#: WHAT WAS WRONG. GAME_ID, DIR, ARTIFACT and PREGAME_FROZEN were module-level
#: constants naming DET_BUF_2026W2, and seven postgame modules read them. So
#: grading a different game meant EDITING THIS FILE -- which is why one of
#: those modules is called run_week2.py. Measured across all 35 fixture-pinned
#: production modules: not one accepted a game, week or slate argument, and 18
#: of them are runnable. A runnable script that silently resolves last month's
#: slate does not fail; it produces a confident artifact for the wrong game.
#:
#: The constants stay, derived from the default, so every existing caller is
#: unaffected. What is new is that they are no longer the ONLY answer.
DEFAULT_GAME_ID = '2026_02_DET_BUF'
DEFAULT_SLATE_ROOT = 'nfl/research/dfs/DET_BUF_2026W2'

#: Environment override, so a different slate can be graded without editing
#: source. Named rather than positional because these paths are read by seven
#: modules and a silent default is what got us here.
SLATE_ENV = 'NFL_POSTGAME_SLATE'


class Slate:
    """Where one slate's frozen pregame and its outcome live.

    Deliberately NOT a dict: the four paths move together, and passing them
    separately is how a grader ends up reading one game's board against
    another game's result -- a defect that would look like a catastrophically
    bad model rather than a wiring error.
    """

    __slots__ = ('game_id', 'root', 'outcome_dir', 'artifact', 'pregame_frozen')

    def __init__(self, game_id: str, root):
        self.game_id = game_id
        self.root = _pl.Path(root)
        self.outcome_dir = self.root / 'POSTGAME_OUTCOME'
        self.artifact = self.outcome_dir / 'OUTCOME.json'
        self.pregame_frozen = self.root / 'frozen'

    def __repr__(self):
        return f'Slate({self.game_id!r}, {self.root})'


def slate(game_id: str = None, root=None) -> Slate:
    """The slate to grade: explicit argument, then environment, then default.

    The default is what every current caller gets, so this is additive. The
    point is that a second slate no longer requires a commit.
    """
    if root is not None:
        return Slate(game_id or _pl.Path(root).name, root)
    env = _os.environ.get(SLATE_ENV, '').strip()
    if env and game_id is None:
        pr = _pl.Path(env)
        pr = pr if pr.is_absolute() else _REPO / pr
        return Slate(pr.name, pr)
    if game_id is None or game_id == DEFAULT_GAME_ID:
        return Slate(DEFAULT_GAME_ID, _REPO / DEFAULT_SLATE_ROOT)
    raise ValueError(
        f'no slate root known for game_id {game_id!r}. Pass root=, or set '
        f'{SLATE_ENV}. Guessing a directory from a game id is how a grader '
        f'silently reads the wrong game.')


_DEFAULT = slate()
GAME_ID = _DEFAULT.game_id
DIR = _DEFAULT.outcome_dir
ARTIFACT = _DEFAULT.artifact
PREGAME_FROZEN = _DEFAULT.pregame_frozen

#: Required top-level keys. A partial box score is not an outcome artifact --
#: grading half the stats and calling it a grade is how a good-looking summary
#: gets written about a bad measurement.
REQUIRED = ('game_id', 'source', 'retrieved_at_utc', 'source_sha256',
            'final_score', 'players')

#: Per-player stats a grade may be computed for. Anything absent is reported
#: NOT_IN_OUTCOME rather than treated as zero.
STATS = ('pass_att', 'pass_cmp', 'pass_yards', 'pass_td', 'interceptions',
         'rush_att', 'rush_yards', 'rush_td',
         'targets', 'receptions', 'rec_yards', 'rec_td')

CODE_MISSING = 'POSTGAME_OUTCOME_NOT_CAPTURED'


def _artifact_game_id(sl: 'Slate'):
    """The game id this slate's own manifest declares, if it declares one.

    For the default slate the expected id is the pinned DET_BUF value, kept so
    nothing about today's behaviour changes. For any other slate there is no
    hardcoded name to compare against, so the gate falls back to what the
    artifact itself says -- which still catches a board graded against the
    WRONG result, because the caller passes `expect_game_id` from the board it
    is grading when it has one.
    """
    if sl is None or str(sl.root) == str(_DEFAULT.root):
        return DEFAULT_GAME_ID
    try:
        d = _json.loads((sl.outcome_dir / 'OUTCOME.json').read_text())
    except Exception:                                            # noqa: BLE001
        return None
    gid = d.get('game_id')
    return gid if isinstance(gid, str) and gid else None


def require(path=None, sl: 'Slate' = None, expect_game_id: str = None) -> Outcome:
    """The gate. No verified outcome artifact, no grade.

    THE GAME IDENTITY IS PART OF THE GATE, and it was the last real pin here.
    The path became addressable while this function still compared the
    artifact's game_id against the module-level GAME_ID, so a second slate
    resolved its own files and was then refused as the WRONG GAME. Paths that
    move while the identity check does not is a parameterisation in name only
    -- exactly the fake this was meant to rule out, and it was caught by
    testing against a slate whose contents DIFFER rather than a byte-identical
    copy.

    Resolution order: an explicit `expect_game_id`, then the slate's id, then
    the default. The check itself is never skipped: grading one game's board
    against another game's result would read as a catastrophically bad model
    rather than as a wiring error.
    """
    sl = sl or (slate(root=pathlib.Path(path).parent.parent) if path else _DEFAULT)
    p = pathlib.Path(path or sl.artifact)
    claim = AC.verify(p, schema=list(REQUIRED), label='outcome artifact')
    if claim.state is not State.PASS:
        return Outcome.blocked(
            CODE_MISSING,
            f'no verified outcome artifact: {claim.detail} Grading is refused '
            f'rather than run against a partial or relayed result. See '
            f'POSTGAME_OUTCOME/CAPTURE_ATTEMPT.json for what was tried.',
            cause=Cause.DATA, spec_version=SPEC_VERSION,
            artifact_path=str(p), claim_code=claim.code,
            claim_reason=claim.evidence.get('reason'))
    d = json.loads(p.read_text())
    if d.get('TEST_FIXTURE_ONLY') and p.resolve() == ARTIFACT.resolve():
        # A fixture may exercise the graders. It may never sit at the real
        # path and be read as the real result -- that is exactly how a
        # synthetic number becomes a quoted one.
        return Outcome.fail(
            'TEST_FIXTURE_AT_PRODUCTION_PATH',
            f'{p} carries TEST_FIXTURE_ONLY. A fixture is NOT_PROSPECTIVE_'
            f'EVIDENCE and may not occupy the outcome artifact path.',
            cause=Cause.GOVERNANCE, artifact_path=str(p))
    want = expect_game_id or _artifact_game_id(sl) or GAME_ID
    if d.get('game_id') != want:
        return Outcome.fail(
            'POSTGAME_OUTCOME_WRONG_GAME',
            f'artifact is for {d.get("game_id")!r}, not {want!r}',
            cause=Cause.DATA, slate=str(sl.root))
    players = d.get('players') or {}
    if not players:
        return Outcome.fail(
            'POSTGAME_OUTCOME_EMPTY',
            'the artifact carries no player rows. An empty result is an '
            'error, not a game in which nobody did anything.',
            cause=Cause.DATA)
    return Outcome.ok(
        'POSTGAME_OUTCOME_VERIFIED', value=d,
        detail=f'{len(players)} player row(s), source {d.get("source")}, '
               f'retrieved {d.get("retrieved_at_utc")}',
        spec_version=SPEC_VERSION, n_players=len(players),
        source=d.get('source'), source_sha256=d.get('source_sha256'),
        artifact_sha256=claim.evidence['sha256'])


def assert_pregame_untouched(sl: 'Slate' = None) -> Outcome:
    """Nothing in the postgame path may write into the frozen pregame set.

    Takes a slate so the check can be run for a game other than the default.
    Leaving it to read the module constant would have made the resolver
    cosmetic: the paths would be addressable while the guard still examined
    DET_BUF, which is the exact shape of a fake parameterisation.
    """
    frozen = (sl or _DEFAULT).pregame_frozen
    files = sorted(p.name for p in frozen.glob('*') if p.is_file())
    expect = {'DKSalaries_showdown.csv', 'sealed_player_draws.npz',
              'sealed_player_draws_manifest.json'}
    extra = sorted(set(files) - expect)
    missing = sorted(expect - set(files))
    if extra or missing:
        return Outcome.fail(
            'PREGAME_FROZEN_SET_MUTATED',
            f'the frozen pregame directory changed: extra {extra}, missing '
            f'{missing}. It is the thing being graded and may not move.',
            cause=Cause.GOVERNANCE, files=files, slate=str(frozen))
    return Outcome.ok('PREGAME_FROZEN_INTACT', value=files,
                      detail=f'{len(files)} frozen pregame file(s) unchanged')


#: Stats a player with no recorded production has. All zero, and that is a
#: MEASUREMENT rather than an imputation -- see `resolve_absent` for the
#: condition under which it is one.
ZERO_LINE = {k: 0.0 for k in STATS}

ZERO_BY_ABSENCE = 'ZERO_NO_RECORDED_PRODUCTION'
UNSCORABLE = 'CLUB_NOT_COVERED_BY_THE_OUTCOME'


def resolve_absent(name, team, result) -> tuple:
    """A board player with no row in the outcome: zero, or unscorable?

    EXCLUDING HIM IS THE WORST OPTION AND IT IS THE TEMPTING ONE. A board
    player who recorded nothing is the model's worst case, and dropping him
    from the grade because he has no row is survivorship -- it grades the
    model only on the players it got onto the field. Frank Gore Jr. was
    projected 4.53 carries and carried 55% of a portfolio.

    The weekly player-stat file carries a row only for a player with a stat
    line, so absence has two possible causes and they must not be conflated:

      no production   his club IS in the outcome, so the club's game was
                      published and he simply did not record a carry, a
                      target or a catch. His line is zeros. A MEASUREMENT.
      not covered     his club is NOT in the outcome, so the game is not
                      published. Nothing is known and nothing is assumed.

    Returns (stat_line_or_None, code).
    """
    clubs = {p.get('team') for p in (result.get('players') or {}).values()}
    if team and team not in clubs:
        return None, UNSCORABLE
    if not team:
        # No club for him at all: the weakest case. Refuse rather than guess
        # which of the two situations he is in.
        return None, UNSCORABLE
    return dict(ZERO_LINE), ZERO_BY_ABSENCE


def percentile_bucket(actual, q: dict) -> str:
    """Where the actual landed in the predicted distribution."""
    if actual is None:
        return 'NOT_IN_OUTCOME'
    if actual < q['p10']:
        return 'BELOW_P10'
    if actual < q['p25']:
        return 'P10_P25'
    if actual <= q['p75']:
        return 'P25_P75'
    if actual <= q['p90']:
        return 'P75_P90'
    return 'ABOVE_P90'


BUCKETS = ('BELOW_P10', 'P10_P25', 'P25_P75', 'P75_P90', 'ABOVE_P90')

#: If the predictive distributions were well calibrated, these are the shares
#: a large sample should approach. ONE GAME CANNOT MEASURE THIS -- the column
#: exists so the ledger accumulates toward it, not so tonight can be scored
#: against it.
NOMINAL = {'BELOW_P10': 0.10, 'P10_P25': 0.15, 'P25_P75': 0.50,
           'P75_P90': 0.15, 'ABOVE_P90': 0.10}
