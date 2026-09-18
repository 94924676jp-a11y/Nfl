"""Phase 12: which artifacts may train a model, and which may only be graded.

THE TWO CLASSES, AND WHY THEY MUST NOT MERGE

  PREGAME_FROZEN_ARTIFACT      sealed before kickoff. It is the THING BEING
                               MEASURED. Feeding it back into a fit is not
                               leakage of the future into the past -- it is
                               worse: it makes the measurement circular, since
                               the model would then be scored against its own
                               training input.
  POSTGAME_TRAINING_ELIGIBLE   the realised outcome. It may train a FUTURE
                               model. It may never touch the board it graded,
                               and it may never be used to re-cut the scope of
                               an evaluation already registered.

THE ASYMMETRY THAT MATTERS. Time does not make an artifact eligible. A stat
line from tonight is training-eligible for next week's model and INELIGIBLE
for tonight's -- same bytes, different answer, because eligibility is a
statement about a pair (artifact, consumer), never about a file.

WHAT THIS FILE REFUSES. `assert_may_train` is the gate a fitting routine
calls. It refuses a pregame frozen artifact outright, refuses an outcome whose
game the consumer's training window includes, and refuses anything it has not
been told about -- an unclassified artifact is a refusal, not a default of
eligible. That default is how a sealed board becomes training data quietly.

WHAT IT DOES NOT DO. It does not scan the filesystem, guess a class from a
path, or decide whether a model is any good. It answers one question and
declines to answer any other.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402

SPEC_VERSION = 'nfl-postgame-eligibility-1'

PREGAME_FROZEN = 'PREGAME_FROZEN_ARTIFACT'
POSTGAME_TRAINING_ELIGIBLE = 'POSTGAME_TRAINING_ELIGIBLE_ARTIFACT'
MARKET_EVALUATION_ONLY = 'MARKET_EVALUATION_ONLY_ARTIFACT'
CLASSES = (PREGAME_FROZEN, POSTGAME_TRAINING_ELIGIBLE, MARKET_EVALUATION_ONLY)

#: Every DET @ BUF artifact, classified. Paths are repo-relative and exact.
#: A path absent from this table is UNCLASSIFIED and refused.
REGISTRY = {
    # --- sealed before kickoff: measured, never trained on -----------------
    'nfl/research/dfs/DET_BUF_2026W2/frozen/sealed_player_draws.npz':
        PREGAME_FROZEN,
    'nfl/research/dfs/DET_BUF_2026W2/frozen/sealed_player_draws_manifest.json':
        PREGAME_FROZEN,
    'nfl/research/dfs/DET_BUF_2026W2/frozen/DKSalaries_showdown.csv':
        PREGAME_FROZEN,
    'nfl/research/dfs/DET_BUF_2026W2/frozen_board_names.json': PREGAME_FROZEN,
    'nfl/research/dfs/DET_BUF_2026W2/PORTFOLIO_CLAUDE_40.csv': PREGAME_FROZEN,
    'nfl/research/dfs/DET_BUF_2026W2/PORTFOLIO_ALTERNATE_40.csv':
        PREGAME_FROZEN,
    'DET_BUF_PREKICKOFF_PROJECTIONS_2026-09-17.md': PREGAME_FROZEN,
    # --- market: evaluation only, in both directions -----------------------
    'nfl/research/market/DET_BUF_2026W2/MAIN_LINE_BOARD.csv':
        MARKET_EVALUATION_ONLY,
    'nfl/research/market/DET_BUF_2026W2/ALL_ROWS.csv': MARKET_EVALUATION_ONLY,
    'nfl/research/market/DET_BUF_2026W2/FULL_LADDER_BOARD.csv':
        MARKET_EVALUATION_ONLY,
    'nfl/research/market/DET_BUF_2026W2_VINTAGES/MARKET_VINTAGES.json':
        MARKET_EVALUATION_ONLY,
    # --- the result: may train a LATER model --------------------------------
    'nfl/research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME/OUTCOME.json':
        POSTGAME_TRAINING_ELIGIBLE,
}

#: The games an outcome is INELIGIBLE to train, keyed by artifact. An outcome
#: may not train any model whose evaluation includes the game it came from.
EMBARGO = {
    'nfl/research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME/OUTCOME.json':
        ('2026_02_DET_BUF',),
}

UNCLASSIFIED = 'ARTIFACT_NOT_CLASSIFIED_FOR_TRAINING'
FROZEN_REFUSED = 'PREGAME_FROZEN_ARTIFACT_MAY_NOT_TRAIN'
MARKET_REFUSED = 'MARKET_MAY_ONLY_EVALUATE'
EMBARGOED = 'OUTCOME_EMBARGOED_FOR_THIS_EVALUATION'


def _rel(path) -> str:
    p = pathlib.Path(path)
    try:
        return str(p.resolve().relative_to(_REPO))
    except ValueError:
        return str(p)


def classify(path) -> Outcome:
    rel = _rel(path)
    cls = REGISTRY.get(rel)
    if cls is None:
        return Outcome.fail(
            UNCLASSIFIED,
            f'{rel} is not in the eligibility registry. An unclassified '
            f'artifact is refused rather than assumed trainable -- assuming '
            f'is how a sealed board becomes training data.',
            cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION,
            artifact=rel, classes=list(CLASSES))
    return Outcome.ok('ARTIFACT_CLASSIFIED', value=cls,
                      detail=f'{rel}: {cls}', spec_version=SPEC_VERSION,
                      artifact=rel, artifact_class=cls)


def assert_may_train(path, *, evaluation_games=()) -> Outcome:
    """May this artifact be an INPUT to a fit evaluated on these games?"""
    got = classify(path)
    if got.state.value != 'PASS':
        return got
    rel, cls = got.evidence['artifact'], got.value
    if cls == PREGAME_FROZEN:
        return Outcome.fail(
            FROZEN_REFUSED,
            f'{rel} is a {PREGAME_FROZEN}. It is the object being measured; '
            f'training on it would score the model against its own input.',
            cause=Cause.GOVERNANCE, artifact=rel, artifact_class=cls)
    if cls == MARKET_EVALUATION_ONLY:
        return Outcome.fail(
            MARKET_REFUSED,
            f'{rel} is market data. OFFICIAL FOOTBALL EVIDENCE MAY UPDATE '
            f'STATE; MARKET DATA MAY ONLY EVALUATE IT.',
            cause=Cause.GOVERNANCE, artifact=rel, artifact_class=cls)
    overlap = sorted(set(EMBARGO.get(rel, ())) & set(evaluation_games))
    if overlap:
        return Outcome.fail(
            EMBARGOED,
            f'{rel} carries the outcome of {overlap}, which this evaluation '
            f'also scores. Same bytes, different answer: it is eligible for a '
            f'model evaluated on later games and not for this one.',
            cause=Cause.GOVERNANCE, artifact=rel, artifact_class=cls,
            overlap=overlap)
    return Outcome.ok(
        'TRAINING_INPUT_PERMITTED', value=cls,
        detail=f'{rel} may train a model evaluated on '
               f'{len(list(evaluation_games))} game(s), none of them embargoed',
        spec_version=SPEC_VERSION, artifact=rel, artifact_class=cls,
        embargoed_games=sorted(EMBARGO.get(rel, ())))
