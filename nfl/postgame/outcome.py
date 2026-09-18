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

SPEC_VERSION = 'nfl-postgame-outcome-1'
GAME_ID = '2026_02_DET_BUF'
DIR = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME'
ARTIFACT = DIR / 'OUTCOME.json'
PREGAME_FROZEN = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/frozen'

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


def require(path=None) -> Outcome:
    """The gate. No verified outcome artifact, no grade."""
    p = pathlib.Path(path or ARTIFACT)
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
    if d.get('game_id') != GAME_ID:
        return Outcome.fail(
            'POSTGAME_OUTCOME_WRONG_GAME',
            f'artifact is for {d.get("game_id")!r}, not {GAME_ID!r}',
            cause=Cause.DATA)
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


def assert_pregame_untouched() -> Outcome:
    """Nothing in the postgame path may write into the frozen pregame set."""
    files = sorted(p.name for p in PREGAME_FROZEN.glob('*') if p.is_file())
    expect = {'DKSalaries_showdown.csv', 'sealed_player_draws.npz',
              'sealed_player_draws_manifest.json'}
    extra = sorted(set(files) - expect)
    missing = sorted(expect - set(files))
    if extra or missing:
        return Outcome.fail(
            'PREGAME_FROZEN_SET_MUTATED',
            f'the frozen pregame directory changed: extra {extra}, missing '
            f'{missing}. It is the thing being graded and may not move.',
            cause=Cause.GOVERNANCE, files=files)
    return Outcome.ok('PREGAME_FROZEN_INTACT', value=files,
                      detail=f'{len(files)} frozen pregame file(s) unchanged')


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
