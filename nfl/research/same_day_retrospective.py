"""Same-day DIAGNOSTIC retrospective: sealed pregame forecasts vs realised play.

THIS IS NOT PROSPECTIVE EVIDENCE AND MUST NEVER BE COUNTED AS ANY.

`postgame.run` refused all 65 week-1 sealed forecasts with
POSTGAME_ARTIFACT_NOT_CURRENTLY_ADMISSIBLE -- three mandatory controls
(`completeness_evidence_class`, `current_blocker_state`,
`prospective_evidence_eligibility`) say these artifacts may not COUNT toward
the decision floors. That gate is correct and is not touched here.

"May not count as evidence" and "may not be looked at" are different claims.
This module answers the second: how wrong was the forecast, and is the error
structured? It reuses the SAME governed pieces -- `actuals` for the realised
side, `postgame.EXACT_ESTIMANDS` for what may be scored at all, and
`postgame.REFUSED_ESTIMANDS` for what is refused by name -- so there is no
second definition of any quantity. What it does not do is write a ledger row,
increment a sample count, or clear a blocker.

CHRONOLOGY IS ENFORCED, NOT ASSUMED. Only seals with
`written_at < kickoff` are scored, and the outcome blob's digest is recorded
on every row. No forecast is regenerated, restamped or rewritten.

ROLE IS DEFINED PREGAME. A receiver's stratum comes from the FORECAST's own
ordering of projected targets, never from what he actually caught. Ranking by
realised production and then reporting that the model mis-ranked players is
circular -- it conditions the stratum on the outcome.

WHICH ROWS GET SCORED IS ALSO DECIDED PREGAME. Version 1.0.0 of this module
refused a row whenever `actuals` carried no record for the player, under the
banner "Not imputed". That reads as conservatism and is not:
`actuals.qb_actuals` and `actuals.receiving_rushing_actuals` emit a record
only for a player who recorded at least one target, carry or dropback, so an
absent record in a COMPLETED game is not an unknown quantity -- for a count
estimand it is the observed value ZERO. Deleting those rows deleted exactly
the forecasts that projected volume onto a player who then recorded nothing:
the over-forecasts. That is selection on the outcome. It reversed the sign of
nine of eleven metrics and moved interval coverage from below nominal to above
it.

`postgame.score_game` already got this right, in this repository, with the
comment this module now follows: A MISSING FIELD IS A MAPPING BUG. A MISSING
PLAYER IS A ZERO. 1,676 of 3,230 rows on the live prospective ledger carry the
resulting `ZERO_BY_COMPLETION` basis.

ZERO IS NOT THE ANSWER FOR EVERY ESTIMAND, so it is not applied to every
estimand. `ABSENCE_SEMANTICS` below classifies each one and carries the
derivation; an estimand whose absence semantics are not derived is REFUSED by
name rather than guessed. The distinction that does the work is between a SUM
over events -- zero events sum to zero -- and a RATE per event, which zero
events leave undefined rather than zero.

ZERO BY COMPLETION IS LICENSED BY COMPLETION. It is applied only where
`postgame.game_finality` has proven the game final from the bytes, and
`score_seal` refuses to run without being handed that proof rather than
trusting its caller.

SELECTION IS DECLARED ON EVERY ROW AND IN THE SUMMARY. `actual_basis` is
OBSERVED or ZERO_BY_COMPLETION on each row, and the summary carries
`outcome_selection_basis`, so a consumer can tell whether a statistic was
computed on a complete set or on a set chosen after the outcome was known.
The pre-repair rule is still reachable, behind `--legacy-outcome-selection`,
for the single purpose of reproducing the superseded artifacts. It stamps
itself as a known leak and its output may not be quoted as a measurement.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.product import forecast_stage as FS                        # noqa: E402
from nfl.research import postgame as PG                             # noqa: E402
from nfl.research import sealed_index as SI                         # noqa: E402
from nfl.research.shadow import actuals as ACT                      # noqa: E402


# ------------------------------------------------- SEALED BOARD DISCOVERY
# DEPTH IS NOT PART OF WHAT A SEALED BOARD IS.
#
# This module, `v2/d7/d7_central_tendency.py` and `market_outcome_audit.py`
# each carried `cfg.glob('*/board.json')`. That shape hard-codes exactly ONE
# directory level below the candidate directory, and 17 of the 121 sealed
# `board.json` files under `nfl/research/live` do not sit there: five
# `2026_01_SF_LA/pre_inactives_*` boards are one level shallower -- the board
# sits in the candidate directory itself and its draws are gzipped -- and
# twelve `REPLAY_C1/*` are a declared exclusion. The three selectors saw 104
# of 121 boards and 65 of 66 R8 boards, and called it every sealed board.
# `D7_ROWS_ALL_SEALS_2026W1.csv` is the published consequence: one seal for
# 2026_01_SF_LA against four to eight for every other game, with ten
# `board.json` on that game's disk.
#
# `sealed_index` had already made exactly this repair for DRAW files and wrote
# down why: "The twelve REPLAY_C1 directories are the proof that the file
# extension was never the cause: they are `.npz` and were missed anyway. Depth
# was." These board readers are now routed through that same entry point
# rather than through a second glob with the same assumption in it.
#
# THE SECOND HALF OF THE SAME DEFECT, AND IT IS NOT THE GLOB. A depth-agnostic
# finder still loses a board if the code that opens it demands one spelling of
# the draw file. `conservation.from_run_dir` required the literal
# `player_draws.npz` and declined five real boards as "missing"; `score_seal`
# below carried the identical presence check, and the five boards it would
# have declined are the same five. Both are repaired here: discovery is by
# `SI.live_draw_files()`, loading is by `SI.load_draws()`, and the stage label
# is resolved by walking up to the directory that NAMES a stage instead of
# assuming it is `d.parent`.

BOARD_DISCOVERY = ('sealed_index.live_draw_files, any depth, either draw '
                   'encoding; REPLAY_C1 excluded BY NAME via '
                   'sealed_index.FENCE_EXCLUDED_NAMESPACES')

_DISCOVERY_VERIFIED = None


def board_config_dir(board_dir):
    """The candidate/stage directory a sealed board belongs to, at ANY depth.

    `d.parent` is the one-level assumption in another costume: for a board
    that sits directly in its candidate directory it reaches past that
    directory and returns the GAME, whose name names no stage, so the stage
    resolves to None and every quarterback admissibility rule keyed on it
    silently changes meaning. Walk up until a segment the stage vocabulary
    recognises, and refuse rather than default if none does.
    """
    root = SI.LIVE_ROOT.resolve()
    cur = pathlib.Path(board_dir).resolve()
    while cur != root and cur.parent != cur:
        if FS.stage_of_dirname(cur.name) is not None:
            return cur
        cur = cur.parent
    return None


def board_stage(board_dir):
    """PRE / POST for a sealed board directory, resolved without a depth."""
    cfg = board_config_dir(board_dir)
    return FS.stage_of_dirname(cfg.name) if cfg is not None else None


def load_sealed_draws(board_dir):
    """The stored draws for a sealed board, either encoding, or None."""
    return SI.load_draws(pathlib.Path(board_dir))


def sealed_board_dirs(game_id=None, label=None):
    """Every sealed board directory under research/live, at any depth.

    `label` filters on the CANDIDATE directory's name -- `V1_CANDIDATE_R8`
    matches a candidate directory ending `_V1_CANDIDATE_R8` -- which is what
    the three old `gdir.glob(f'*_{label}')` selectors meant by it.
    """
    global _DISCOVERY_VERIFIED
    if _DISCOVERY_VERIFIED is None:
        # Set BEFORE the cross-check, which itself calls this function. A
        # reader that forgets to call the guard is the failure mode the guard
        # exists for, so it is not left to a caller to remember.
        _DISCOVERY_VERIFIED = {}
        _DISCOVERY_VERIFIED = assert_board_discovery_complete()
    out = set()
    for f in SI.live_draw_files():
        d = f.parent
        if not (d / 'board.json').exists():
            continue
        if game_id is not None and SI.game_id_of(f) != game_id:
            continue
        if label is not None:
            cfg = board_config_dir(d)
            if cfg is None or not cfg.name.endswith('_' + str(label)):
                continue
        out.add(d)
    return sorted(out)


def assert_board_discovery_complete():
    """Every discoverable board is reachable by the route above, or say so.

    Discovery runs through the stored DRAWS, so a sealed board whose draws
    were never written would be invisible to it -- a new way to lose 17 of
    121 without noticing. This is the cross-check, and it is deliberately
    depth-agnostic on both sides: `rglob`, not a level count. Measured
    2026-09-15: 121 board.json on disk, 12 in the declared REPLAY_C1
    exclusion, 109 reached, 0 unreachable.
    """
    reached = {str(d) for d in sealed_board_dirs()}
    on_disk, excluded = set(), 0
    for b in SI.LIVE_ROOT.rglob('board.json'):
        ns = b.relative_to(SI.LIVE_ROOT).parts[0]
        if ns in SI.FENCE_EXCLUDED_NAMESPACES:
            excluded += 1
            continue
        on_disk.add(str(b.parent))
    missed = sorted(on_disk - reached)
    if missed:
        raise RuntimeError(
            f'SEALED_BOARD_WITHOUT_STORED_DRAWS: {len(missed)} sealed '
            f'board(s) carry a board.json that the draw-file route cannot '
            f'reach, so a board reader would silently omit them: '
            f'{missed[:6]}. An unreachable board is an error with a name, '
            f'not a smaller frame.')
    return {'boards_on_disk': len(on_disk) + excluded,
            'declared_exclusions': excluded,
            'reached': len(reached), 'unreachable': 0}

# 2.0.0, not 1.0.1: which rows are scored is part of what the number MEANS,
# so a statistic from this module may not be compared with one from 1.0.0.
SPEC_VERSION = 'same-day-retrospective/2.0.0'
NOT_EVIDENCE = ('DIAGNOSTIC ONLY. Not prospective evidence, not a ledger row, '
                'does not count toward any sample floor, and clears no '
                'blocker.')

COLUMNS = ('game_id', 'kickoff_utc', 'player', 'gsis_id', 'team', 'position',
           'metric', 'layer', 'forecast_stage', 'seal_written_at', 'run_id',
           'role_tier', 'model_mean', 'model_median',
           'q10', 'q25', 'q50', 'q75', 'q90',
           'actual', 'actual_basis', 'absence_class',
           'forecast_minus_actual', 'abs_error', 'pct_error',
           'pit', 'in_50', 'in_80', 'in_90', 'crps',
           'n_draws', 'completeness', 'qb3_configuration',
           'qb3_contaminated', 'qb3_contamination_basis', 'outcome_sha256')

# --------------------------------------------------- ABSENCE SEMANTICS
# WHAT AN ABSENT REALISED RECORD MEANS, PER ESTIMAND, WITH THE DERIVATION.
#
# The reflex fix for the leak repaired here is "missing means zero". Applied
# globally that is a second defect: it would report a rate as 0 for a player
# who never generated the denominator, which is a different claim from "the
# rate was low". Each estimand is therefore classified from ITS OWN
# definition, and a class is one of exactly four.
ZERO_IF_ABSENT = 'ZERO_IF_ABSENT'          # absence IS an observed zero
MISSING_IF_ABSENT = 'MISSING_IF_ABSENT'    # absence means unobserved
NOT_APPLICABLE = 'NOT_APPLICABLE'          # the estimand does not apply here
UNRESOLVED = 'UNRESOLVED'                  # not derivable -- refuse, don't guess

# The generic derivations, stated once so the per-metric entries can cite them.
_D_COUNT = ('COUNT OF EVENTS. The realised value is the number of qualifying '
            'play-by-play rows carrying this player. A player who appears on '
            'no qualifying row generated no such events, and the count of an '
            'empty set is 0. `actuals` omits him because the counter was '
            'never incremented, not because the count is unknown.')
_D_SUM = ('SUM OF A PER-EVENT QUANTITY OVER THE PLAYER\'S EVENTS. The sum '
          'over zero events is 0 by the definition of an empty sum -- it is '
          'not a rate and carries no division. Negative per-event values '
          'exist (a loss on a completion or a carry) but every term is '
          'absent here, so the sum is exactly 0 and not merely near it.')
_D_RATE = ('RATIO WITH A REALISED DENOMINATOR. Zero events leaves 0/0, which '
           'is undefined, not zero. Reporting 0 would assert the player was '
           'maximally inefficient when in fact he was never measured.')

ABSENCE_SEMANTICS = {
    # ---- QB counts -------------------------------------------------------
    'qb/att': (ZERO_IF_ABSENT, _D_COUNT + ' Here: throws, i.e. pass_attempt '
               'rows that are not sacks (actuals.py:126-131).'),
    'qb/cmp': (ZERO_IF_ABSENT, _D_COUNT + ' Here: complete_pass on a throw. '
               'Completions cannot exceed attempts, and both are 0.'),
    'qb/ptd': (ZERO_IF_ABSENT, _D_COUNT + ' Here: pass_touchdown on a throw.'),
    'qb/int': (ZERO_IF_ABSENT, _D_COUNT + ' Here: interception on a throw.'),
    'qb/sacks': (ZERO_IF_ABSENT, _D_COUNT + ' Here: sack rows charged to the '
                 'passer.'),
    'qb/db': (ZERO_IF_ABSENT, 'IDENTITY OVER THREE COUNTS: db = att + sacks '
              '+ scr (actuals.py:154, enforced at qb_v1.py:267). All three '
              'terms are absent-and-therefore-zero, so the identity gives 0 '
              'rather than it being asserted separately.'),
    # ---- QB yardage ------------------------------------------------------
    'qb/pyds': (ZERO_IF_ABSENT, _D_SUM + ' Here: passing_yards summed over '
                'the passer\'s throws (actuals.py:129). A quarterback who '
                'threw no pass has a 0-term sum. NOTE the asymmetry with a '
                'quarterback who DID throw: he gets a record, so this branch '
                'never fires for him and his negative or zero yardage is '
                'read as OBSERVED.'),
    # ---- Non-QB counts ---------------------------------------------------
    'rushing/carries': (ZERO_IF_ABSENT, _D_COUNT + ' Here: rush_attempt rows '
                        'with this player as rusher (actuals.py:208-209).'),
    'receiving/targets': (ZERO_IF_ABSENT, _D_COUNT + ' Here: pass_attempt '
                          'rows naming this player as receiver '
                          '(actuals.py:200-201).'),
    'receiving/receptions': (ZERO_IF_ABSENT, _D_COUNT + ' Here: complete_pass '
                             'on a target. Bounded above by targets, which '
                             'are also 0.'),
    # ---- Non-QB yardage --------------------------------------------------
    'receiving/receiving_yards': (
        ZERO_IF_ABSENT, _D_SUM + ' Here: receiving_yards summed over the '
        'player\'s targets (actuals.py:203). Zero targets is a 0-term sum. '
        'This is the estimand that most looks like it needs a rate and does '
        'not: yards PER TARGET would be undefined, but total yards is a sum.'),
    # ---- Team ------------------------------------------------------------
    'team_volume/team_carries': (
        MISSING_IF_ABSENT,
        'TEAM AGGREGATE, not a player quantity. Every completed game has '
        'offensive rows for both clubs, so an absent team key is a JOIN OR '
        'INGESTION FAILURE, not a club that ran zero plays. Zeroing it would '
        'convert a data defect into a realised outcome -- precisely the '
        'failure this repair exists to remove. (Not reached by this module: '
        'team rows are skipped here and scored by postgame.score_game.)'),
}

# Estimands refused by name upstream, carried here so the classification table
# is complete rather than only covering what happens to be scoreable today.
ABSENCE_SEMANTICS_REFUSED = {
    'team_volume/team_off_snaps': (
        NOT_APPLICABLE, 'A SNAP COUNT FROM A DIFFERENT FEED. The forecast '
        'estimand is not derivable from play-by-play at all, so absence in '
        '`actuals` says nothing about the realised value. The participation '
        'feed is blocked; the quantity is neither zero nor missing-at-random, '
        'it is out of scope for this source.'),
    'team_volume/team_dropbacks_part': (
        NOT_APPLICABLE, 'PARTICIPATION-MATCHED COUNT. Only a SURROGATE upper '
        'bound is computable here (actuals.py:97-102), so no absence rule '
        'applies to the estimand actually forecast.'),
    'team_volume/team_targets': (
        MISSING_IF_ABSENT, 'Team aggregate; same argument as team_carries. '
        'Additionally the estimand match itself is unverified upstream.'),
    'team_volume/team_rz_carries': (
        MISSING_IF_ABSENT, 'Team aggregate; same argument as team_carries.'),
    'rushing/rushing_yards': (
        ZERO_IF_ABSENT, _D_SUM + ' The SEMANTICS are settled -- a player with '
        'zero carries has zero rushing yards -- but the estimand is refused '
        'upstream as NOT_MODELLED, so there is no forecast to pair with the '
        'zero. Classified, not scored.'),
    'receiving/receiving_td': (
        ZERO_IF_ABSENT, _D_COUNT + ' Semantics settled; refused upstream '
        'because TD attribution across rushing and receiving is unreconciled '
        'with the allocation layer. Classified, not scored.'),
    'rushing/rushing_td': (
        ZERO_IF_ABSENT, _D_COUNT + ' Semantics settled; refused upstream for '
        'the same attribution reason. Classified, not scored.'),
}

# Estimands that are NOT forecast today but that a reader will reach for the
# moment zero-completion is discussed, because they are the trap. Recorded so
# the answer is written down before someone derives it wrongly under time
# pressure.
ABSENCE_SEMANTICS_DERIVED_RATES = {
    'derived/yards_per_target': (MISSING_IF_ABSENT, _D_RATE),
    'derived/catch_rate': (MISSING_IF_ABSENT, _D_RATE),
    'derived/yards_per_carry': (MISSING_IF_ABSENT, _D_RATE),
    'derived/yards_per_attempt': (MISSING_IF_ABSENT, _D_RATE),
    'derived/completion_rate': (MISSING_IF_ABSENT, _D_RATE),
    'derived/yards_per_dropback': (MISSING_IF_ABSENT, _D_RATE),
    'derived/target_share': (
        MISSING_IF_ABSENT, 'RATIO WITH A TEAM DENOMINATOR. Unlike a per-event '
        'rate the denominator IS observed for a player who recorded nothing, '
        'so the value is 0/team_targets = 0 whenever team_targets > 0 -- but '
        'that is a DERIVED quantity this module does not forecast, and it is '
        'left MISSING rather than computed on the side, because a share is '
        'only meaningful against a stated denominator.'),
}

# Refusal codes this module emits. Every one is NAMED and every one is
# counted; a row that is neither scored nor named is a defect.
R_NO_DRAW_ROW = 'NO_IDENTIFIED_DRAW_ROW'
R_FIELD_NOT_IN_ACTUALS = 'ESTIMAND_FIELD_NOT_IN_ACTUALS'
R_UNOBSERVED = 'REALISED_VALUE_UNOBSERVED_NOT_ZERO'
R_NOT_APPLICABLE = 'ESTIMAND_NOT_APPLICABLE_TO_THIS_ROW'
R_UNRESOLVED = 'ABSENCE_SEMANTICS_UNRESOLVED'
R_LEGACY_LEAK = 'NO_REALISED_VALUE_FOR_THIS_PLAYER'

# ------------------------------------------------ THE DECISION, ONCE
# WHY A KIND IS RETURNED AND NOT A CODE.
#
# Two scorers consume this: the retrospective and the market grader. They
# publish into artifacts with DIFFERENT established refusal vocabularies --
# this module's legacy code is NO_REALISED_VALUE_FOR_THIS_PLAYER, the market
# audit's is NO_REALISED_VALUE, and both appear in already-published files
# that must stay reproducible. Those strings are ARTIFACT VOCABULARY. Which
# branch fires is the DECISION, and the decision is what may not drift.
#
# So `resolve_realised` owns the decision and returns a KIND; each caller maps
# the kind into its own vocabulary. One ladder, two dialects -- rather than two
# ladders held equivalent by an assertion in a test.
KIND_LEGACY_OUTCOME_SELECTION = 'LEGACY_OUTCOME_SELECTION'
KIND_FIELD_NOT_IN_ACTUALS = 'FIELD_NOT_IN_ACTUALS'
KIND_UNOBSERVED = 'UNOBSERVED'
KIND_NOT_APPLICABLE = 'NOT_APPLICABLE'
KIND_UNRESOLVED = 'UNRESOLVED_ABSENCE_SEMANTICS'
REFUSAL_KINDS = (KIND_LEGACY_OUTCOME_SELECTION, KIND_FIELD_NOT_IN_ACTUALS,
                 KIND_UNOBSERVED, KIND_NOT_APPLICABLE, KIND_UNRESOLVED)


def resolve_realised(src, field, metric, final, legacy_outcome_selection=False):
    """The realised value for one forecast row, or a NAMED refusal kind.

    THE SINGLE DECISION POINT for what an absent realised record means. Both
    scorers in this repository call it; neither implements the ladder itself.

    Returns `(actual, basis, absence_class)` when the row is gradable, with
    `basis` either 'OBSERVED' or 'ZERO_BY_COMPLETION'; otherwise
    `(None, ('REFUSED', kind, detail), absence_class)` where `kind` is one of
    `REFUSAL_KINDS` and the caller renders it in its own vocabulary.

    THE ORDER OF THE BRANCHES IS THE REPAIR. A record that EXISTS is read. A
    record that does not exist is resolved from the estimand's OWN absence
    class -- zero for a count or a sum over events, a named refusal for
    anything else. What never happens is a row being dropped because of what
    the player went on to do.

    `final` is `postgame.game_finality(...)` for this game. Zero by completion
    is licensed by completion and is asserted HERE, so no caller can inherit
    the licence from its own control flow and later lose it in an edit.
    """
    cls, why = ABSENCE_SEMANTICS.get(
        metric, (UNRESOLVED, 'this estimand is not in ABSENCE_SEMANTICS, so '
                             'what an absent record means for it has not been '
                             'derived. Refused rather than guessed.'))
    if src is not None and src.get(field) is not None:
        return float(src[field]), 'OBSERVED', cls
    if legacy_outcome_selection:
        # THE LEAK, REPRODUCED DELIBERATELY. Reachable only behind the
        # caller's --legacy-outcome-selection, which stamps the whole run.
        return None, ('REFUSED', KIND_LEGACY_OUTCOME_SELECTION, None), cls
    if src is not None:
        # A MISSING FIELD IS A MAPPING BUG. The record exists, so the player
        # DID appear; a key the record does not carry is a broken estimand map
        # and must never default to zero. This is the Nacua failure (74
        # receiving yards scored as 0) that postgame.py documents.
        return None, ('REFUSED', KIND_FIELD_NOT_IN_ACTUALS, field), cls
    if cls == ZERO_IF_ABSENT:
        # A MISSING PLAYER IS A ZERO -- the game is complete, this player
        # appears on no qualifying play, and the estimand is a count or a sum
        # over those plays.
        if not (final or {}).get('final'):
            raise RuntimeError(
                'ZERO_COMPLETION_WITHOUT_PROVEN_FINALITY: the '
                'zero-completion branch was reached without a proven-final '
                'game_finality result. An absent player is a realised zero '
                'only because the game is over; in a part-published game he '
                'is an unknown, and zeroing him would manufacture exactly the '
                'over-forecast rows this repair exists to keep.')
        return 0.0, 'ZERO_BY_COMPLETION', cls
    if cls == MISSING_IF_ABSENT:
        return None, ('REFUSED', KIND_UNOBSERVED, why), cls
    if cls == NOT_APPLICABLE:
        return None, ('REFUSED', KIND_NOT_APPLICABLE, why), cls
    return None, ('REFUSED', KIND_UNRESOLVED, why), cls

SELECTION_COMPLETE = 'COMPLETE_INCLUDING_ZERO_BY_COMPLETION'
SELECTION_LEAKED = 'SELECTED_ON_REALISED_VALUE'
LEAK_WARNING = (
    'THIS RUN REPRODUCES A KNOWN SELECTION LEAK ON PURPOSE. Rows whose '
    'realised value was zero were deleted, which removes the over-forecasts '
    'and nothing else. Every statistic below is conditioned on the outcome '
    'and none of it is a measurement of the model. It exists only to '
    'reproduce the superseded artifacts byte-for-byte.')


def crps_sample(draws, y):
    d = np.sort(np.asarray(draws, float))
    n = len(d)
    if not n:
        return None
    t1 = float(np.abs(d - y).mean())
    i = np.arange(1, n + 1)
    t2 = float(2 * np.sum((2 * i - n - 1) * d) / (n * n))
    return t1 - 0.5 * t2


def pit_of(draws, y):
    """Randomised PIT for a discrete forecast.

    A COUNT FORECAST IS DISCRETE, so the plain `mean(draws <= y)` piles PIT
    mass at the atoms and a histogram of it looks miscalibrated even when the
    forecast is perfect. The randomised version spreads each atom's mass
    across its interval, which is the standard correction and is stated here
    rather than left for a reader to wonder about.
    """
    d = np.asarray(draws, float)
    n = len(d)
    if not n:
        return None
    lo = float((d < y).mean())
    eq = float((d == y).mean())
    rng = np.random.default_rng(20260913)
    return float(lo + eq * rng.random())


def interval_flags(draws, y):
    d = np.asarray(draws, float)
    out = {}
    for lab, lvl in (('in_50', 50), ('in_80', 80), ('in_90', 90)):
        a = (100 - lvl) / 2.0
        lo, hi = np.percentile(d, [a, 100 - a])
        out[lab] = bool(lo <= y <= hi)
    return out


def role_tiers(board, names):
    """Pregame role, from the FORECAST's own projected volume. Never postgame.

    Receivers are tiered by projected targets within their club, rushers by
    projected carries. The forecast made this ordering before kickoff; using it
    keeps the stratum independent of what happened.
    """
    tiers = {}
    for fam, metric, tags in (('receiving', 'receiving/targets',
                               ('PRIMARY_RECEIVER', 'SECONDARY_RECEIVER',
                                'DEPTH_RECEIVER')),
                              ('rushing', 'rushing/carries',
                               ('PRIMARY_RUSHER', 'SECONDARY_RUSHER',
                                'DEPTH_RUSHER'))):
        by_team = collections.defaultdict(list)
        for p in board.get('players') or []:
            m = (p.get('metrics') or {}).get(metric)
            if not isinstance(m, dict) or m.get('mean') is None:
                continue
            by_team[p.get('team')].append((float(m['mean']), p['gsis_id']))
        for team, lst in by_team.items():
            lst.sort(reverse=True)
            for i, (_, pid) in enumerate(lst):
                tiers[(pid, fam)] = tags[0] if i == 0 else (
                    tags[1] if i <= 2 else tags[2])
    return tiers


def _render_refusal(kind, why):
    """A refusal KIND in THIS module's published vocabulary. Strings preserved.

    These exact reason codes and detail texts appear in already-published
    artifacts, so they are reproduced verbatim rather than harmonised with the
    market grader's. The vocabularies differ; the decision behind them does
    not, and that is the property worth protecting.
    """
    if kind == KIND_LEGACY_OUTCOME_SELECTION:
        return R_LEGACY_LEAK, ('the player has no row in the authoritative '
                               'play-by-play for this estimand. Not imputed.')
    if kind == KIND_FIELD_NOT_IN_ACTUALS:
        return R_FIELD_NOT_IN_ACTUALS, (
            f'{why!r} is not a key of a realised record that DOES exist for '
            f'this player. That is a mapping bug, not a zero.')
    if kind == KIND_UNOBSERVED:
        return R_UNOBSERVED, why
    if kind == KIND_NOT_APPLICABLE:
        return R_NOT_APPLICABLE, why
    if kind == KIND_UNRESOLVED:
        return R_UNRESOLVED, why
    raise ValueError(
        f'UNRENDERED_REFUSAL_KIND: {kind!r} has no rendering in this module. '
        f'A refusal kind the scorer cannot name is a row that would vanish '
        f'from the accounting, which is the defect class this module exists '
        f'to remove.')


def score_seal(gid, ko, sealed_dir, rows, outcome_sha, names,
               finality=None, legacy_outcome_selection=False):
    """Diagnostic rows for one sealed forecast.

    Reads an absent realised record as the observed value its estimand says it
    is, and refuses by name where that value is not derivable. `finality` must
    be the `postgame.game_finality` result for this game: ZERO_BY_COMPLETION
    is licensed by completion and this function will not take completion on
    trust from its caller.
    """
    if not legacy_outcome_selection:
        if not isinstance(finality, dict) or not finality.get('final'):
            raise RuntimeError(
                f'ZERO_COMPLETION_WITHOUT_PROVEN_FINALITY: {gid} was passed '
                f'to score_seal without a proven-final game_finality result '
                f'({finality!r}). An absent player is a realised zero only '
                f'because the game is over; in a part-published game it is an '
                f'unknown, and scoring it as zero would manufacture exactly '
                f'the over-forecast rows this module was repaired to keep.')
    d = pathlib.Path(sealed_dir)
    board_p = d / 'board.json'
    man_p = d / 'player_draws_manifest.json'
    if not board_p.exists() or not man_p.exists():
        return [], {'game_id': gid, 'dir': str(d),
                    'status': 'NO_BOARD_OR_MANIFEST'}
    board = json.loads(board_p.read_text())
    wa = (board.get('freshness') or {}).get('written_at')
    if not wa or str(wa) >= str(ko):
        return [], {'game_id': gid, 'dir': str(d),
                    'status': 'NOT_PREGAME', 'written_at': wa,
                    'kickoff_utc': ko}
    man = json.loads(man_p.read_text())
    # EITHER ENCODING, AND NO DEPTH ASSUMPTION. `d / 'player_draws.npz'` is
    # the presence check that made `conservation.from_run_dir` decline five
    # real boards as "missing": SF_LA's five pre-inactives seals store
    # `player_draws.npz.gz`. `SI.load_draws` reads both.
    draws = load_sealed_draws(d)
    if draws is None:
        return [], {'game_id': gid, 'dir': str(d),
                    'status': 'NO_STORED_DRAWS',
                    'detail': 'nine percentiles cannot support CRPS and none '
                              'is computed from them'}
    stage = board_stage(d)
    qb = ACT.qb_actuals(rows)
    rr = ACT.receiving_rushing_actuals(rows)
    tiers = role_tiers(board, names)
    cfg = board.get('qb3_configuration') or {}
    # CONTAMINATION IS DERIVED, NOT READ FROM A FIELD THE BOARD MAY PREDATE.
    #
    # `qb3_configuration` was added to the board on 2026-09-13 at ~21:20Z. The
    # 1 PM boards were sealed at 15:46Z, so the field is ABSENT on every one of
    # them -- and reading it gave `qb3_contaminated: 0` across 268 rows, which
    # would have presented 112 contaminated quarterback rows as clean. An
    # absent flag is not a false flag. The season-boundary condition is
    # recomputed here from the same governed function the allocation uses.
    _season = int(str(gid).split('_')[0])
    _week = int(str(gid).split('_')[1])
    _opener = {}
    try:
        from nfl.production.nonqb import qb_allocation as _QA
        _pd = _QA.previous_primary_detail(_season, _week)
        _opener = {k: bool((v or {}).get('is_season_opener'))
                   for k, v in _pd.items()}
    except Exception:
        _opener = {}
    out, refused = [], []
    for p in board.get('players') or []:
        pid = p.get('gsis_id')
        for metric, (family, field) in PG.EXACT_ESTIMANDS.items():
            if family == 'team':
                continue
            if metric not in (p.get('metrics') or {}):
                continue
            # THE FORECAST SIDE IS RESOLVED FIRST, AND ON PURPOSE.
            #
            # Whether a row is gradable must be decided by what existed at
            # forecast time -- is there an identified draw row for this player
            # and metric -- and never by what the player went on to do. The
            # previous order asked the outcome first, so the outcome decided
            # the sample.
            lay = metric.split('/')[0]
            ids = ((man.get('layers') or {}).get(lay) or {}).get('row_ids') or []
            key = metric.replace('/', '__')
            if pid not in ids or key not in draws.files:
                refused.append({'game_id': gid, 'player': names.get(pid, pid),
                                'gsis_id': pid, 'metric': metric,
                                'reason': R_NO_DRAW_ROW,
                                'detail': 'no identified draw row for this '
                                          'player and metric. Refused on the '
                                          'FORECAST side, before the outcome '
                                          'is consulted.'})
                continue
            v = np.asarray(draws[key][ids.index(pid)], float)

            src = qb.get(pid) if family == 'qb' else rr.get(pid)
            # THE LADDER LIVES IN `resolve_realised` AND NOWHERE ELSE. What
            # happens here is only the rendering of its verdict into THIS
            # artifact's refusal vocabulary.
            y, basis, cls = resolve_realised(
                src, field, metric, finality,
                legacy_outcome_selection=legacy_outcome_selection)
            if y is None:
                _, kind, why = basis
                reason, detail = _render_refusal(kind, why)
                refused.append({'game_id': gid, 'player': names.get(pid, pid),
                                'gsis_id': pid, 'metric': metric,
                                'reason': reason, 'detail': detail})
                continue
            mean = float(v.mean())
            fam_tier = 'receiving' if lay == 'receiving' else (
                'rushing' if lay == 'rushing' else None)
            tier = tiers.get((pid, fam_tier)) if fam_tier else (
                'QB' if lay == 'qb' else None)
            teamcfg = (cfg.get(p.get('team')) or {})
            row = {
                'game_id': gid, 'kickoff_utc': ko,
                'player': names.get(pid, pid), 'gsis_id': pid,
                'team': p.get('team'), 'position': p.get('position'),
                'metric': metric, 'layer': lay, 'forecast_stage': stage,
                'seal_written_at': wa, 'run_id': board.get('run_id'),
                'role_tier': tier,
                'model_mean': round(mean, 4),
                'model_median': round(float(np.median(v)), 4),
                'actual': y,
                'actual_basis': basis,
                'absence_class': cls,
                'forecast_minus_actual': round(mean - y, 4),
                'abs_error': round(abs(mean - y), 4),
                'pct_error': (round((mean - y) / y * 100.0, 4) if y else ''),
                'pit': round(pit_of(v, y), 6),
                'crps': round(crps_sample(v, y), 6),
                'n_draws': int(v.size),
                'completeness': board.get('completeness'),
                'qb3_configuration': teamcfg.get('configuration'),
                'qb3_contaminated': bool(
                    lay == 'qb' and (
                        teamcfg.get('week1_specification_defect')
                        if teamcfg else _opener.get(p.get('team'), False))),
                'qb3_contamination_basis': (
                    'board qb3_configuration' if teamcfg
                    else 'derived from previous_primary_detail; the board '
                         'predates the qb3_configuration field'),
                'outcome_sha256': outcome_sha,
            }
            for lab, q in (('q10', 10), ('q25', 25), ('q50', 50),
                           ('q75', 75), ('q90', 90)):
                row[lab] = round(float(np.percentile(v, q)), 4)
            row.update(interval_flags(v, y))
            out.append(row)
    n_zero = sum(1 for r in out if r['actual_basis'] == 'ZERO_BY_COMPLETION')
    return out, {'game_id': gid, 'dir': str(d), 'status': 'SCORED',
                 'n_rows': len(out), 'written_at': wa, 'stage': stage,
                 'run_id': board.get('run_id'), 'n_refused': len(refused),
                 'n_zero_by_completion': n_zero,
                 'n_observed': len(out) - n_zero,
                 'finality': (finality or {}).get('code'),
                 'outcome_selection_basis': (
                     SELECTION_LEAKED if legacy_outcome_selection
                     else SELECTION_COMPLETE),
                 'refused_by_reason': dict(collections.Counter(
                     r['reason'] for r in refused)),
                 'refused': refused[:40]}


def _cluster_se(x, labels):
    """Cluster-robust standard error of a MEAN.

        se = sqrt( G/(G-1) * sum_g ( sum_{i in g} (x_i - xbar) )^2 ) / n

    This is the ordinary CRVE for the mean, written out rather than imported
    so the convention it uses is readable. G/(G-1) is the finite-cluster
    correction; at small G it is not a fix, it is a reminder -- with 5 or 9
    clusters no interval here is trustworthy at its nominal level and the
    cluster count travels beside every number so a reader can see that.

    Returns None when there are fewer than two clusters, because a single
    cluster carries no between-cluster information and any number produced
    from it would be a naive SE wearing a clustered label.
    """
    x = np.asarray(x, float)
    n = len(x)
    if n == 0:
        return None
    g = collections.defaultdict(list)
    for xi, lab in zip(x, labels):
        g[lab].append(xi)
    G = len(g)
    if G < 2:
        return None
    xbar = x.mean()
    ss = sum((sum(v) - len(v) * xbar) ** 2 for v in g.values())
    return float(np.sqrt(G / (G - 1.0) * ss) / n)


# NAIVE STANDARD ERRORS ARE REFUSED, NOT COMPUTED AND LABELLED.
#
# Player-rows inside one game move together (a team's targets are a fixed pool
# the players share; a quarterback's attempts, completions and yards are three
# views of one afternoon). Treating them as independent understates the
# spread, and in this repository it has understated it roughly threefold.
# Emitting a naive SE beside a clustered one invites the smaller number to be
# quoted, so only the clustered ones are emitted at all.
NAIVE_SE_REFUSED = (
    'A NAIVE SE IS NOT EMITTED. Rows within a game, and within a player-game, '
    'are not independent observations. Only game-clustered and '
    'player-game-clustered standard errors appear here, each beside its '
    'cluster count.')


def _stats(rows, key=None):
    """Descriptive error statistics. No adequacy word is used anywhere."""
    if not rows:
        return None
    e = np.array([r['forecast_minus_actual'] for r in rows], float)
    a = np.array([r['abs_error'] for r in rows], float)
    c = np.array([r['crps'] for r in rows], float)
    pit = np.array([r['pit'] for r in rows], float)
    cov50 = np.array([1.0 if r['in_50'] else 0.0 for r in rows], float)
    g_lab = [r['game_id'] for r in rows]
    pg_lab = [(r['game_id'], r['gsis_id']) for r in rows]
    se_g = _cluster_se(e, g_lab)
    se_pg = _cluster_se(e, pg_lab)
    se_cov_g = _cluster_se(cov50, g_lab)
    n_zero = sum(1 for r in rows
                 if r.get('actual_basis') == 'ZERO_BY_COMPLETION')
    return {
        'n': len(rows),
        'n_rows_is_not_a_sample_size': (
            'rows are per player-game-metric; the unit these errors vary in '
            'is the GAME. n_game_clusters is the sample size.'),
        'n_game_clusters': len(set(g_lab)),
        'n_player_game_clusters': len(set(pg_lab)),
        'n_zero_by_completion': n_zero,
        'n_observed': len(rows) - n_zero,
        'se_convention': NAIVE_SE_REFUSED,
        'se_mean_signed_error_game_clustered': (
            round(se_g, 4) if se_g is not None else None),
        'z_mean_signed_error_game_clustered': (
            round(float(e.mean() / se_g), 4) if se_g else None),
        'se_mean_signed_error_player_game_clustered': (
            round(se_pg, 4) if se_pg is not None else None),
        # WITHIN ONE METRIC, EVERY PLAYER-GAME HOLDS EXACTLY ONE ROW, so
        # clustering by player-game is arithmetically the NAIVE SE wearing a
        # clustered label. It binds only where several markets share a
        # player-game -- the pooled strata, where a quarterback contributes
        # seven rows and a receiver three. Saying so here stops a per-metric
        # table from reading as two independent robustness layers when it is
        # one, and stops the smaller number from being quoted as clustered.
        'player_game_clustering_degenerate': (
            len(set(pg_lab)) == len(rows)),
        'player_game_clustering_note': (
            'one row per player-game in this stratum: the player-game SE '
            'here IS the naive SE and must not be read as clustered. Read '
            'the game-clustered figure.'
            if len(set(pg_lab)) == len(rows) else
            'several rows share a player-game in this stratum, so the '
            'player-game SE is a genuine second clustering.'),
        'z_mean_signed_error_player_game_clustered': (
            round(float(e.mean() / se_pg), 4) if se_pg else None),
        'se_coverage_50_game_clustered': (
            round(se_cov_g, 4) if se_cov_g is not None else None),
        'n_model_above_actual': int((e > 0).sum()),
        'n_model_below_actual': int((e < 0).sum()),
        'mean_signed_error': round(float(e.mean()), 4),
        'median_signed_error': round(float(np.median(e)), 4),
        'mean_abs_error': round(float(a.mean()), 4),
        'mean_crps': round(float(c.mean()), 4),
        'coverage_50': round(float(np.mean([r['in_50'] for r in rows])), 4),
        'coverage_80': round(float(np.mean([r['in_80'] for r in rows])), 4),
        'coverage_90': round(float(np.mean([r['in_90'] for r in rows])), 4),
        'pit_mean': round(float(pit.mean()), 4),
        'pit_q25': round(float(np.percentile(pit, 25)), 4),
        'pit_q75': round(float(np.percentile(pit, 75)), 4),
        # CARRIED UNCHANGED AND NOT INTERPRETABLE. `pit_of` builds its RNG
        # inside the function from a fixed seed and draws one uniform, so
        # every row in a run receives the identical u = 0.21444212299020937
        # (WS22 §1 item 11). That is a constant shift, not randomisation. It
        # is a SEPARATE defect from the one this version repairs and is
        # deliberately left untouched so that exactly one thing changed here;
        # it is flagged rather than quietly republished.
        'pit_interpretable': False,
        'pit_defect': ('SHARED_CONSTANT_RANDOMISATION: pit_of seeds an RNG '
                       'per call and draws one uniform, so the same u is '
                       'applied to every row. Unrepaired here by design.'),
    }


def _by(rows, keyfn):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyfn(r)].append(r)
    return {str(k): _stats(v) for k, v in sorted(g.items(), key=lambda x: str(x[0]))}


def compression_diagnostic(rows, metric):
    """Does the model spread players LESS than reality did?

    Reported as the OLS slope of actual on model and the ratio of standard
    deviations. A slope above 1 means the realised spread is wider than the
    forecast spread -- the forecast compressed. Both are descriptive; neither
    is a test, and no equivalence margin was predeclared.
    """
    s = [r for r in rows if r['metric'] == metric]
    if len(s) < 4:
        return {'metric': metric, 'n': len(s),
                'status': 'INSUFFICIENT_ROWS_FOR_A_SLOPE'}
    m = np.array([r['model_mean'] for r in s], float)
    y = np.array([r['actual'] for r in s], float)
    if m.std(ddof=1) == 0:
        return {'metric': metric, 'n': len(s), 'status': 'NO_MODEL_SPREAD'}
    slope = float(np.polyfit(m, y, 1)[0])
    return {
        'metric': metric, 'n': len(s),
        'ols_actual_on_model_slope': round(slope, 4),
        'sd_model': round(float(m.std(ddof=1)), 4),
        'sd_actual': round(float(y.std(ddof=1)), 4),
        'sd_ratio_model_over_actual': round(
            float(m.std(ddof=1) / y.std(ddof=1)), 4) if y.std(ddof=1) else None,
        'corr': round(float(np.corrcoef(m, y)[0, 1]), 4),
        'reading': ('slope > 1 and sd ratio < 1 both indicate the forecast '
                    'spread players less than the outcome did'),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='same-day diagnostic retrospective')
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--games', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seal', default='last',
                    choices=('first', 'last', 'all'),
                    help='which pregame seal per game: the earliest, the most '
                         'informed, or every one (each labelled).')
    ap.add_argument('--outcome-blob', default=None,
                    help='score against an ALREADY-STORED outcome blob '
                         'instead of re-fetching. A reproduction must not '
                         'depend on the network being up, and must not '
                         'silently score against restated upstream bytes.')
    ap.add_argument('--legacy-outcome-selection', action='store_true',
                    help='REPRODUCE THE KNOWN SELECTION LEAK: delete every '
                         'row whose realised value was zero, as version '
                         '1.0.0 did. For reproducing superseded artifacts '
                         'only. The output stamps itself as not a '
                         'measurement.')
    a = ap.parse_args(argv)

    o = (PG.stored_outcome(a.outcome_blob) if a.outcome_blob
         else PG.fetch_outcomes(a.season))
    if o.state is not State.PASS:
        raise SystemExit(f'OUTCOME_FETCH_REFUSED: {o.code} {o.detail}')
    blob = o.evidence['blob']
    outcome_sha = o.evidence['sha256']
    allrows = PG._rows(blob)
    names = ACT.names(allrows)

    from nfl.capture import coverage as CV
    plan = CV.load_week_plan(a.season, 1)
    ko_of = {}
    for g in plan.value or []:
        k = g.kickoff_utc
        ko_of[g.game_id] = (k.isoformat().replace('+00:00', 'Z')
                            if hasattr(k, 'isoformat') else str(k))

    want = a.games.split(',')
    rows, seals, skipped = [], [], []
    for gid in want:
        sub = [r for r in allrows if r.get('game_id') == gid]
        if not sub:
            skipped.append({'game_id': gid,
                            'status': 'NOT_IN_AUTHORITATIVE_OUTCOME_SOURCE'})
            continue
        fin = PG.game_finality(sub)
        if not fin['final']:
            skipped.append({'game_id': gid, 'status': PG.NOT_FINAL,
                            'unmet': fin['unmet']})
            continue
        ko = ko_of.get(gid)
        if not ko:
            skipped.append({'game_id': gid, 'status': 'NO_KICKOFF_IN_PLAN'})
            continue
        cands = []
        for sd in sealed_board_dirs(game_id=gid, label='V1_CANDIDATE_R8'):
            j = json.loads((sd / 'board.json').read_text())
            wa = (j.get('freshness') or {}).get('written_at')
            if wa and str(wa) < str(ko):
                cands.append((str(wa), sd))
        if not cands:
            skipped.append({'game_id': gid, 'status': 'NO_PREGAME_SEAL'})
            continue
        cands.sort()
        pick = ([cands[0]] if a.seal == 'first'
                else [cands[-1]] if a.seal == 'last' else cands)
        for wa, sd in pick:
            r, s = score_seal(gid, ko, sd, sub, outcome_sha, names,
                              finality=fin,
                              legacy_outcome_selection=a.legacy_outcome_selection)
            rows += r
            seals.append(s)

    # A STAGE THAT PRODUCED NOTHING HAS NOT SUCCEEDED.
    #
    # Every recurring failure in this project is a step that returned nothing,
    # or something partial, being read as success. An empty retrospective is
    # an error with a name, not a clean slate with no findings.
    if not rows:
        raise SystemExit(
            'EMPTY_RETROSPECTIVE_RESULT: no row was scored from '
            f'{len(seals)} seal(s) over {len(want)} requested game(s). An '
            'empty result is an error, not a finding. Seal statuses: '
            f'{[s.get("status") for s in seals]}; skipped: '
            f'{[s.get("status") for s in skipped]}.')
    missing_cols = sorted({c for c in COLUMNS if c not in rows[0]})
    if missing_cols:
        raise SystemExit(
            f'RETROSPECTIVE_SCHEMA_INCOMPLETE: scored rows are missing '
            f'{missing_cols}. A column guessed at write time is how this '
            f'project exported 7,926 rows with every meaningful field blank.')

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in COLUMNS})

    clean = [r for r in rows if not r['qb3_contaminated']]
    contam = [r for r in rows if r['qb3_contaminated']]
    summary = {
        'artifact': 'SUNDAY_1PM_OUTCOME_AUDIT',
        'spec_version': SPEC_VERSION,
        'governance': NOT_EVIDENCE,
        'why_this_is_not_the_prospective_ledger': (
            'postgame.run refuses every one of these sealed forecasts with '
            'POSTGAME_ARTIFACT_NOT_CURRENTLY_ADMISSIBLE -- three mandatory '
            'controls say they may not COUNT toward the decision floors. That '
            'gate is correct and untouched. This audit measures how wrong the '
            'forecasts were, which is a different question from whether they '
            'are admissible as evidence.'),
        'outcome_source': {'blob': str(blob), 'sha256': outcome_sha,
                           'n_pbp_rows': len(allrows),
                           'finality': 'proven per game from the bytes'},
        'seal_selection': a.seal,
        'outcome_selection_basis': (SELECTION_LEAKED
                                    if a.legacy_outcome_selection
                                    else SELECTION_COMPLETE),
        'outcome_selection_note': (
            LEAK_WARNING if a.legacy_outcome_selection else
            'A forecast row is graded because a draw row for it exists, '
            'which was decided pregame. An absent realised record in a '
            'COMPLETED game is read as the value its estimand defines -- '
            'zero for a count or a sum over events -- so the over-forecasts '
            'stay in the sample. Nothing here is imputed: every value is '
            'either OBSERVED or ZERO_BY_COMPLETION, and the per-row basis '
            'says which.'),
        'absence_semantics': {
            'scored_estimands': {k: {'class': v[0], 'derivation': v[1]}
                                 for k, v in ABSENCE_SEMANTICS.items()},
            'refused_upstream': {k: {'class': v[0], 'derivation': v[1]}
                                 for k, v in
                                 ABSENCE_SEMANTICS_REFUSED.items()},
            'derived_rates_not_forecast': {
                k: {'class': v[0], 'derivation': v[1]}
                for k, v in ABSENCE_SEMANTICS_DERIVED_RATES.items()},
        },
        'n_rows': len(rows),
        'n_rows_zero_by_completion': sum(
            1 for r in rows if r['actual_basis'] == 'ZERO_BY_COMPLETION'),
        'n_rows_observed': sum(
            1 for r in rows if r['actual_basis'] == 'OBSERVED'),
        'n_refused': sum(s.get('n_refused', 0) for s in seals),
        'refused_by_reason': dict(collections.Counter(
            k for s in seals
            for k, v in (s.get('refused_by_reason') or {}).items()
            for _ in range(v))),
        'n_rows_qb3_contaminated': len(contam),
        'strata_note': ('QB rows from season-opener rooms are carried in a '
                        'SEPARATE contaminated stratum and never pooled into '
                        'conclusions about non-QB layers.'),
        'overall_excluding_qb3_contaminated': _stats(clean),
        'overall_qb3_contaminated_stratum': _stats(contam),
        'by_metric': _by(clean, lambda r: r['metric']),
        'by_metric_including_contaminated': _by(rows, lambda r: r['metric']),
        'by_actual_basis': _by(rows, lambda r: r['actual_basis']),
        'by_position': _by(clean, lambda r: r['position']),
        'by_game': _by(clean, lambda r: r['game_id']),
        'by_role_tier': _by(clean, lambda r: r['role_tier']),
        'by_layer': _by(clean, lambda r: r['layer']),
        'by_completeness': _by(clean, lambda r: r['completeness']),
        'compression': {m: compression_diagnostic(clean, m)
                        for m in ('receiving/targets', 'receiving/receptions',
                                  'receiving/receiving_yards',
                                  'rushing/carries')},
        'estimands_refused_by_name': PG.REFUSED_ESTIMANDS,
        'what_cannot_be_concluded': [
            'one slate is not a sample. Every figure here is descriptive and '
            'none is a test.',
            'games are not independent observations. Standard errors here are '
            'clustered by game and by player-game and no naive SE is emitted, '
            'but a clustered SE on five or nine clusters is still a wide, '
            'poorly-determined interval and no equivalence margin has been '
            'predeclared for any of these quantities.',
            'no word of adequacy -- unbiased, stable, closed, correct -- '
            'applies to anything here. Failing to reject a null on nine '
            'clusters is not evidence of adequacy.',
            'pit_mean and the PIT quartiles are NOT interpretable: pit_of '
            'applies one shared uniform to every row. That defect is carried '
            'forward unrepaired so that exactly one thing changed in this '
            'version.',
            'no threshold may be chosen because it would have worked today.',
            'a forecast that was wrong today is not thereby a defect, and one '
            'that was right is not thereby correct.'],
    }
    sp = out.with_suffix('.summary.json')
    sp.write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(f'{len(rows)} diagnostic row(s) -> {out}')
    print(f'summary -> {sp}')
    print(f'seals used: {len(seals)}, games skipped: {len(skipped)}')
    print(f"selection: {summary['outcome_selection_basis']}  "
          f"observed={summary['n_rows_observed']} "
          f"zero_by_completion={summary['n_rows_zero_by_completion']} "
          f"refused={summary['n_refused']}")
    if a.legacy_outcome_selection:
        print('WARNING: ' + LEAK_WARNING)
    ov = summary['overall_excluding_qb3_contaminated']
    if ov:
        print(f"overall (ex-contaminated): n={ov['n']} "
              f"mean signed={ov['mean_signed_error']:+.3f} "
              f"below={ov['n_model_below_actual']} above={ov['n_model_above_actual']} "
              f"cov50={ov['coverage_50']:.3f} cov80={ov['coverage_80']:.3f} "
              f"cov90={ov['coverage_90']:.3f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
